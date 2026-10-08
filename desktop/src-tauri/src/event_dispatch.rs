//! Pure decisions for the daemon-event subscribe loop.
//!
//! The loop in `subscribe_daemon_events` used to inline three behaviours that
//! were hard to test in isolation: seq dedupe, the subscribe-then-backfill
//! gap-fill, and "drop frame if it predates the cursor". This module exposes
//! them as pure functions over a small state struct.

use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::{Mutex, OnceLock};

use serde_json::Value;

/// In-process bookkeeping per (daemon connection) for the daemon-event stream.
pub struct SubscribeState {
    /// Highest `seq` we've already delivered to the frontend.
    pub last_seq: u64,
    anchored: bool,
    last_at: f64,
    floor_at: Option<f64>,
    replay_head: u64,
    known: HashSet<(u64, u64)>,
    known_order: VecDeque<(u64, u64)>,
    fresh: HashSet<(u64, u64)>,
    /// Seqs we've seen recently — dedupes the overlap between a live frame
    /// and a backfilled frame that carry the same seq.
    seen: HashSet<u64>,
    /// FIFO of `seen` for bounded eviction; capped at `seen_cap`.
    seen_order: VecDeque<u64>,
    seen_cap: usize,
}

impl SubscribeState {
    pub fn new(seen_cap: usize) -> Self {
        Self {
            last_seq: 0,
            anchored: false,
            last_at: 0.0,
            floor_at: None,
            replay_head: 0,
            known: HashSet::new(),
            known_order: VecDeque::new(),
            fresh: HashSet::new(),
            seen: HashSet::new(),
            seen_order: VecDeque::new(),
            seen_cap,
        }
    }

    /// Returns `true` if the seq is new (and records it); `false` if already seen.
    /// The seen set is bounded so a long-running session can't grow unbounded.
    pub fn mark_seen(&mut self, seq: u64) -> bool {
        if self.seen.contains(&seq) {
            return false;
        }
        self.seen.insert(seq);
        self.seen_order.push_back(seq);
        while self.seen_order.len() > self.seen_cap {
            if let Some(old) = self.seen_order.pop_front() {
                self.seen.remove(&old);
            }
        }
        true
    }

    /// Move `last_seq` forward only — never backwards. Returns whether it changed.
    pub fn bump_seq(&mut self, seq: u64) -> bool {
        self.anchored = true;
        if seq > self.last_seq {
            self.last_seq = seq;
            true
        } else {
            false
        }
    }

    pub fn cursor(&self) -> Option<u64> {
        self.anchored.then_some(self.last_seq)
    }

    // A plain restart can also restore a counter below our cursor (unpersisted seqs): replay from zero only what is stamped after the last frame seen, or re-anchor at the head when nothing was seen. Returns whether to replay.
    pub fn rewind(&mut self, head: u64) -> bool {
        self.anchored = true;
        self.seen.clear();
        self.seen_order.clear();
        if self.last_at > 0.0 {
            self.floor_at = Some(self.last_at);
            self.replay_head = head;
            self.last_seq = 0;
            true
        } else {
            self.last_seq = head;
            false
        }
    }

    pub fn observe(&mut self, frames: &[Value]) {
        for frame in frames {
            if let Some(at) = frame.get("at").and_then(|v| v.as_f64()) {
                self.last_at = self.last_at.max(at);
            }
            let persisted = frame.get("event").and_then(|v| v.as_str()) != Some("activity.changed");
            if let Some(id) = identity(frame).filter(|_| persisted) {
                if self.known.insert(id) {
                    self.known_order.push_back(id);
                    while self.known_order.len() > KNOWN_CAP {
                        if let Some(old) = self.known_order.pop_front() {
                            self.known.remove(&old);
                        }
                    }
                }
            }
        }
    }

    // Replay pages arrive in append order: what follows the last frame this client already knew was raised after the reset, whatever its clock says. A page with no known frame could be restored history, so only its newest few are trusted. Call before accepting the page.
    pub fn begin_page(&mut self, frames: &[Value]) {
        self.fresh.clear();
        if self.floor_at.is_none() {
            return;
        }
        let after = frames
            .iter()
            .rposition(|f| identity(f).map_or(false, |id| self.known.contains(&id)))
            .map_or(frames.len().saturating_sub(UNANCHORED_TAIL), |i| i + 1);
        self.fresh.extend(frames[after..].iter().filter_map(identity));
    }

    // The floor guards only the one replay page after a rewind, so a daemon clock that later moves back never silences live frames.
    pub fn end_replay(&mut self) {
        self.floor_at = None;
        self.replay_head = 0;
        self.fresh.clear();
    }

    // Above the head the daemon reported at the reset a frame is new whatever its clock says; at or below it only a later stamp tells a startup alert from history.
    pub fn accept(&mut self, frame: &Value) -> bool {
        let at = frame.get("at").and_then(|v| v.as_f64());
        let seq = frame.get("seq").and_then(|v| v.as_u64());
        let fresh = identity(frame).map_or(false, |id| self.fresh.contains(&id));
        if let (Some(floor), Some(at)) = (self.floor_at, at) {
            if !fresh && at <= floor && seq.map_or(true, |s| s <= self.replay_head) {
                return false;
            }
        }
        if let Some(seq) = seq {
            if !self.mark_seen(seq) {
                return false;
            }
        }
        self.observe(std::slice::from_ref(frame));
        true
    }
}

// One cursor per daemon, shared by the live stream and the inactive poller, so a connection switch neither drops nor replays events.
pub fn daemon_states() -> &'static Mutex<HashMap<String, SubscribeState>> {
    static STATES: OnceLock<Mutex<HashMap<String, SubscribeState>>> = OnceLock::new();
    STATES.get_or_init(|| Mutex::new(HashMap::new()))
}

pub const STATE_SEEN_CAP: usize = 1024;
const KNOWN_CAP: usize = 4096;
const UNANCHORED_TAIL: usize = 5;

fn identity(frame: &Value) -> Option<(u64, u64)> {
    let seq = frame.get("seq").and_then(|v| v.as_u64())?;
    let at = frame.get("at").and_then(|v| v.as_f64())?;
    Some((seq, at.to_bits()))
}

/// What the loop should do with the frame the daemon just sent.
#[derive(Debug, Eq, PartialEq)]
pub enum SubscribeAction {
    /// First connect on this endpoint — anchor at `next_seq`, no replay.
    AnchorAt(u64),
    /// Subsequent connect — backfill via `host.events.history(after_seq=prev)`.
    BackfillFrom(u64),
    /// Deliver this live frame; bump cursor.
    Deliver { seq: Option<u64> },
    /// Already delivered (live ↔ replay overlap). Ignore.
    DuplicateSeq,
    /// Frame the loop doesn't care about (malformed, no `event`, etc.).
    Ignore,
}

/// Classify a frame coming off `host.events.subscribe`.
///
/// `state` is mutated for the live-frame path (mark_seen, bump_seq) and to rewind a
/// daemon whose seq went backwards; otherwise the handshake decides from `cursor()`,
/// so the caller can choose to backfill (still using the pre-handshake cursor)
/// and only commit to the new anchor after the backfill walk finishes.
pub fn classify_frame(state: &mut SubscribeState, frame: &Value) -> SubscribeAction {
    let event = match frame.get("event").and_then(|v| v.as_str()) {
        Some(s) => s,
        None => return SubscribeAction::Ignore,
    };
    if event == "ping" {
        // Transport keepalive — already did its job by resetting the read timeout.
        return SubscribeAction::Ignore;
    }
    if event == "subscribed" {
        let anchor = frame.get("next_seq").and_then(|v| v.as_u64());
        return if state.anchored {
            SubscribeAction::BackfillFrom(state.last_seq)
        } else if let Some(a) = anchor {
            SubscribeAction::AnchorAt(a)
        } else {
            SubscribeAction::AnchorAt(0)
        };
    }
    let seq = frame.get("seq").and_then(|v| v.as_u64());
    if !state.accept(frame) {
        return SubscribeAction::DuplicateSeq;
    }
    if let Some(seq) = seq {
        state.bump_seq(seq);
    }
    SubscribeAction::Deliver { seq }
}

pub const NOTIFIABLE_KINDS: [&str; 6] = [
    "agent.message",
    "wg.done",
    "approval.request",
    "clarification.request",
    "schedule.failed",
    "budget.threshold",
];

// Notifiable kinds raise a native notification; the output kinds only refresh the inbox of a connection that is not active.
pub const POLL_KINDS: [&str; 8] = [
    "agent.message",
    "wg.done",
    "approval.request",
    "clarification.request",
    "schedule.failed",
    "budget.threshold",
    "output.created",
    "output.updated",
];

pub struct PollOutcome {
    pub to_notify: Vec<Value>,
    pub next_cursor: u64,
}

// cursor=None is first sight: anchor at head, notify nothing (no startup storm). With a cursor: notify returned frames past it, then jump to head — events older than the fetched window are skipped on purpose (anti-storm; the durable inbox still lists them).
pub fn classify_poll(cursor: Option<u64>, events: &[Value], next_seq: Option<u64>) -> PollOutcome {
    let max_seq = events
        .iter()
        .filter_map(|e| e.get("seq").and_then(|v| v.as_u64()))
        .max();
    let head = next_seq.into_iter().chain(max_seq).max().unwrap_or(0);
    match cursor {
        None => PollOutcome { to_notify: Vec::new(), next_cursor: head },
        Some(c) => {
            let to_notify: Vec<Value> = events
                .iter()
                .filter(|e| {
                    e.get("seq")
                        .and_then(|v| v.as_u64())
                        .map(|s| s > c)
                        .unwrap_or(false)
                })
                .cloned()
                .collect();
            PollOutcome { to_notify, next_cursor: head.max(c) }
        }
    }
}

// The daemon's counter only grows, so a head below the cursor the request carried means its history was reset; a head below a cursor that moved on since is just a late answer.
pub fn history_was_reset(requested: Option<u64>, next_seq: Option<u64>) -> bool {
    matches!((requested, next_seq), (Some(r), Some(n)) if n < r)
}

// A first poll anchors without banners, but rows filed before it may be missing from an inbox loaded earlier.
pub fn first_sight_touches_inbox(cursor: Option<u64>, events: &[Value]) -> bool {
    cursor.is_none()
        && events.iter().any(|e| {
            matches!(e.get("event").and_then(|v| v.as_str()), Some("output.created" | "output.updated"))
        })
}

pub fn poll_into(
    state: &mut SubscribeState,
    requested: Option<u64>,
    events: &[Value],
    next_seq: Option<u64>,
) -> Vec<Value> {
    if history_was_reset(requested, next_seq) {
        state.rewind(next_seq.unwrap_or(0));
        return Vec::new();
    }
    state.begin_page(events);
    let outcome = classify_poll(state.cursor(), events, next_seq);
    let fresh = outcome
        .to_notify
        .into_iter()
        .filter(|e| e.get("seq").and_then(|v| v.as_u64()).is_some() && state.accept(e))
        .collect();
    state.observe(events);
    state.end_replay();
    state.bump_seq(outcome.next_cursor);
    fresh
}

// A sibling route of the active daemon is left to the live stream only while that stream is up; a down stream must not silence its siblings.
pub fn should_poll(
    id: &str,
    key: &str,
    active_id: &str,
    active_key: Option<&str>,
    active_online: bool,
    role: Option<&str>,
) -> bool {
    if id == active_id || role == Some("member") {
        return false;
    }
    !(active_online && active_key == Some(key))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn fresh() -> SubscribeState {
        SubscribeState::new(8)
    }

    // mark_seen / bump_seq -----------------------------------------------------

    #[test]
    fn mark_seen_first_call_returns_true() {
        let mut s = fresh();
        assert!(s.mark_seen(1));
    }

    #[test]
    fn mark_seen_duplicate_returns_false() {
        let mut s = fresh();
        assert!(s.mark_seen(1));
        assert!(!s.mark_seen(1));
    }

    #[test]
    fn mark_seen_evicts_oldest_past_cap() {
        let mut s = SubscribeState::new(3);
        for i in 1..=5 {
            assert!(s.mark_seen(i));
        }
        // After inserting 1..=5 with cap=3, only the last three (3, 4, 5) survive — 1 and 2 aged out.
        assert!(!s.mark_seen(3));
        assert!(!s.mark_seen(4));
        assert!(!s.mark_seen(5));
        // Resubmitting evicted seqs counts as new again.
        assert!(s.mark_seen(1));
        // The next insert evicts the oldest of the survivors (3).
        assert!(s.mark_seen(2));
        assert!(s.mark_seen(3));  // 3 was just evicted by inserting 2
    }

    #[test]
    fn bump_seq_is_monotone() {
        let mut s = fresh();
        assert!(s.bump_seq(5));
        assert_eq!(s.last_seq, 5);
        assert!(!s.bump_seq(3));        // backwards: refused
        assert_eq!(s.last_seq, 5);
        assert!(s.bump_seq(10));
        assert_eq!(s.last_seq, 10);
    }

    // classify_frame -----------------------------------------------------------

    #[test]
    fn keepalive_ping_is_ignored_and_does_not_touch_state() {
        let mut s = fresh();
        s.bump_seq(7);
        let action = classify_frame(&mut s, &json!({"event": "ping", "id": "tauri-stream"}));
        assert_eq!(action, SubscribeAction::Ignore);
        assert_eq!(s.last_seq, 7);
    }

    #[test]
    fn handshake_first_connect_anchors_at_next_seq() {
        let mut s = fresh();
        let action = classify_frame(
            &mut s,
            &json!({"event": "subscribed", "next_seq": 42}),
        );
        assert_eq!(action, SubscribeAction::AnchorAt(42));
    }

    #[test]
    fn handshake_with_prior_cursor_triggers_backfill() {
        let mut s = fresh();
        s.bump_seq(7);
        let action = classify_frame(
            &mut s,
            &json!({"event": "subscribed", "next_seq": 99}),
        );
        assert_eq!(action, SubscribeAction::BackfillFrom(7));
    }

    #[test]
    fn handshake_without_next_seq_anchors_at_zero() {
        let mut s = fresh();
        let action = classify_frame(&mut s, &json!({"event": "subscribed"}));
        assert_eq!(action, SubscribeAction::AnchorAt(0));
    }

    #[test]
    fn live_new_seq_is_delivered_and_bumps_cursor() {
        let mut s = fresh();
        let action = classify_frame(
            &mut s,
            &json!({"event": "config_changed", "seq": 5, "data": {}}),
        );
        assert_eq!(action, SubscribeAction::Deliver { seq: Some(5) });
        assert_eq!(s.last_seq, 5);
    }

    #[test]
    fn live_duplicate_seq_is_dropped() {
        let mut s = fresh();
        let _ = classify_frame(&mut s, &json!({"event": "wg.post", "seq": 5}));
        let action = classify_frame(&mut s, &json!({"event": "wg.post", "seq": 5}));
        assert_eq!(action, SubscribeAction::DuplicateSeq);
        // Cursor didn't move on the duplicate.
        assert_eq!(s.last_seq, 5);
    }

    #[test]
    fn live_without_seq_is_delivered_without_bump() {
        // Older daemon (pre v0.4.52) emitted frames with no `seq`. Deliver them
        // anyway so the client sees state changes; just don't dedupe.
        let mut s = fresh();
        let action = classify_frame(&mut s, &json!({"event": "session_changed"}));
        assert_eq!(action, SubscribeAction::Deliver { seq: None });
        assert_eq!(s.last_seq, 0);
    }

    #[test]
    fn frame_without_event_is_ignored() {
        let mut s = fresh();
        let action = classify_frame(&mut s, &json!({"data": {"profile": "doc"}}));
        assert_eq!(action, SubscribeAction::Ignore);
    }

    // classify_poll -------------------------------------------------------------

    fn ev(seq: u64) -> Value {
        json!({"event": "agent.message", "seq": seq})
    }

    fn seqs(out: &PollOutcome) -> Vec<u64> {
        out.to_notify
            .iter()
            .filter_map(|e| e.get("seq").and_then(|v| v.as_u64()))
            .collect()
    }

    #[test]
    fn poll_first_sight_anchors_at_head_without_notifying() {
        let out = classify_poll(None, &[ev(5), ev(6)], Some(6));
        assert!(out.to_notify.is_empty());
        assert_eq!(out.next_cursor, 6);
    }

    #[test]
    fn poll_first_sight_with_no_events_anchors_at_next_seq() {
        let out = classify_poll(None, &[], Some(10));
        assert!(out.to_notify.is_empty());
        assert_eq!(out.next_cursor, 10);
    }

    #[test]
    fn poll_with_cursor_notifies_only_frames_past_it() {
        let out = classify_poll(Some(5), &[ev(5), ev(6), ev(7)], Some(7));
        assert_eq!(seqs(&out), vec![6, 7]);
        assert_eq!(out.next_cursor, 7);
    }

    #[test]
    fn poll_with_cursor_and_no_new_events_keeps_cursor() {
        let out = classify_poll(Some(7), &[], None);
        assert!(out.to_notify.is_empty());
        assert_eq!(out.next_cursor, 7);
    }

    #[test]
    fn poll_cursor_never_moves_backwards_on_stale_response() {
        let out = classify_poll(Some(9), &[ev(3)], Some(2));
        assert!(out.to_notify.is_empty());
        assert_eq!(out.next_cursor, 9);
    }

    #[test]
    fn poll_with_cursor_jumps_to_head_skipping_events_beyond_the_window() {
        // Busy daemon: only the recent tail returned, head far ahead → cursor jumps to head, older-than-window events skipped on purpose.
        let out = classify_poll(Some(5), &[ev(108), ev(109), ev(110)], Some(200));
        assert_eq!(seqs(&out), vec![108, 109, 110]);
        assert_eq!(out.next_cursor, 200);
    }

    #[test]
    fn notifiable_kinds_cover_interrupts_but_not_wg_blocked() {
        // wg.blocked is a derived fold of a BLOCKED wg.done close, not an emitted event — blocked workgroups surface via wg.done.
        assert!(NOTIFIABLE_KINDS.contains(&"agent.message"));
        assert!(NOTIFIABLE_KINDS.contains(&"wg.done"));
        assert!(!NOTIFIABLE_KINDS.contains(&"wg.blocked"));
        assert!(!NOTIFIABLE_KINDS.contains(&"wg.post"));
        assert!(NOTIFIABLE_KINDS.contains(&"clarification.request"));
    }

    #[test]
    fn poll_kinds_are_the_notifiable_ones_plus_the_inbox_changes() {
        for kind in NOTIFIABLE_KINDS {
            assert!(POLL_KINDS.contains(&kind));
        }
        assert!(POLL_KINDS.contains(&"output.created"));
        assert!(POLL_KINDS.contains(&"output.updated"));
        assert_eq!(POLL_KINDS.len(), NOTIFIABLE_KINDS.len() + 2);
    }

    // poll_into -----------------------------------------------------------------

    fn polled(state: &mut SubscribeState, events: &[Value], next: Option<u64>) -> Vec<u64> {
        let requested = state.cursor();
        poll_into(state, requested, events, next)
            .iter()
            .filter_map(|e| e.get("seq").and_then(|v| v.as_u64()))
            .collect()
    }

    #[test]
    fn a_daemon_first_seen_by_the_poller_anchors_without_notifying() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        assert!(polled(&mut s, &[ev(5), ev(6)], Some(6)).is_empty());
        assert_eq!(s.cursor(), Some(6));
    }

    #[test]
    fn a_daemon_with_no_events_yet_still_counts_as_anchored() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        assert!(polled(&mut s, &[], Some(0)).is_empty());
        assert_eq!(polled(&mut s, &[ev(1)], Some(1)), vec![1]);
    }

    #[test]
    fn the_poller_continues_where_the_live_stream_left_off() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &json!({"event": "agent.message", "seq": 40}));
        assert_eq!(polled(&mut s, &[ev(40), ev(41), ev(42)], Some(42)), vec![41, 42]);
        assert_eq!(s.cursor(), Some(42));
    }

    #[test]
    fn the_live_stream_backfills_from_where_the_poller_left_off() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[], Some(30));
        let _ = polled(&mut s, &[ev(31)], Some(33));
        let action = classify_frame(&mut s, &json!({"event": "subscribed", "next_seq": 35}));
        assert_eq!(action, SubscribeAction::BackfillFrom(33));
        assert_eq!(classify_frame(&mut s, &ev(31)), SubscribeAction::DuplicateSeq);
    }

    #[test]
    fn the_live_stream_on_an_empty_daemon_anchors_once_then_backfills() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[], Some(0));
        let action = classify_frame(&mut s, &json!({"event": "subscribed", "next_seq": 0}));
        assert_eq!(action, SubscribeAction::BackfillFrom(0));
    }

    #[test]
    fn a_frame_the_live_stream_delivered_is_never_notified_again_by_the_poller() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[], Some(10));
        let _ = classify_frame(&mut s, &ev(11));
        let _ = classify_frame(&mut s, &ev(12));
        assert_eq!(polled(&mut s, &[ev(11), ev(12), ev(13)], Some(13)), vec![13]);
    }

    #[test]
    fn a_poll_after_the_daemon_reset_its_history_starts_over_from_zero() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[at(4990, 100.0)], Some(5000));
        assert!(polled(&mut s, &[], Some(3)).is_empty());
        assert_eq!(s.cursor(), Some(0));
        assert_eq!(polled(&mut s, &[at(1, 90.0), at(2, 110.0), at(3, 120.0)], Some(3)), vec![1, 2, 3]);
        assert_eq!(s.cursor(), Some(3));
    }

    #[test]
    fn a_stream_handshake_backfills_from_the_cursor_and_leaves_the_reset_to_the_history_answer() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &ev(9));
        let action = classify_frame(&mut s, &json!({"event": "subscribed", "next_seq": 3}));
        assert_eq!(action, SubscribeAction::BackfillFrom(9));
        assert_eq!(s.cursor(), Some(9));
    }

    #[test]
    fn a_late_poll_answer_is_not_a_reset() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[], Some(40));
        let requested = s.cursor();
        let _ = classify_frame(&mut s, &ev(41));
        assert!(poll_into(&mut s, requested, &[], Some(40)).is_empty());
        assert_eq!(s.cursor(), Some(41));
        assert!(polled(&mut s, &[ev(41)], Some(41)).is_empty());
        assert_eq!(polled(&mut s, &[ev(41), ev(42)], Some(42)), vec![42]);
    }

    #[test]
    fn a_reset_is_a_head_below_the_cursor_the_request_carried() {
        assert!(history_was_reset(Some(40), Some(3)));
        assert!(!history_was_reset(Some(40), Some(40)));
        assert!(!history_was_reset(None, Some(3)));
        assert!(!history_was_reset(Some(40), None));
        assert!(!history_was_reset(Some(0), Some(0)));
    }

    #[test]
    fn a_first_poll_refreshes_the_inbox_only_when_its_page_changed_it() {
        assert!(first_sight_touches_inbox(None, &[json!({"event": "output.created", "seq": 3})]));
        assert!(first_sight_touches_inbox(None, &[json!({"event": "output.updated", "seq": 3})]));
        assert!(!first_sight_touches_inbox(None, &[ev(3)]));
        assert!(!first_sight_touches_inbox(Some(2), &[json!({"event": "output.created", "seq": 3})]));
    }

    #[test]
    fn an_anchor_at_zero_still_counts_as_anchored() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        s.bump_seq(0);
        assert_eq!(s.cursor(), Some(0));
        let action = classify_frame(&mut s, &json!({"event": "subscribed", "next_seq": 0}));
        assert_eq!(action, SubscribeAction::BackfillFrom(0));
    }

    #[test]
    fn the_poller_leaves_the_active_route_and_members_alone() {
        assert!(!should_poll("a", "daemon:x", "a", Some("daemon:x"), true, Some("admin")));
        assert!(!should_poll("b", "daemon:y|connection:b", "a", Some("daemon:x"), true, Some("member")));
        assert!(should_poll("b", "daemon:y", "a", Some("daemon:x"), true, Some("admin")));
    }

    #[test]
    fn a_sibling_route_is_polled_only_while_the_active_stream_is_down() {
        assert!(!should_poll("local", "daemon:x", "remote", Some("daemon:x"), true, Some("admin")));
        assert!(should_poll("local", "daemon:x", "remote", Some("daemon:x"), false, Some("admin")));
        assert!(should_poll("local", "daemon:x", "remote", None, true, Some("admin")));
    }

    fn at(seq: u64, at: f64) -> Value {
        json!({"event": "agent.message", "seq": seq, "at": at})
    }

    #[test]
    fn a_restart_that_restores_a_lower_counter_replays_nothing_old() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[], Some(30));
        let _ = polled(&mut s, &[at(31, 100.0), at(32, 101.0)], Some(42));
        let requested = s.cursor();
        assert!(poll_into(&mut s, requested, &[], Some(40)).is_empty());
        let old = [at(31, 100.0), at(32, 101.0)];
        assert!(polled(&mut s, &old, Some(40)).is_empty());
        assert_eq!(polled(&mut s, &[at(31, 100.0), at(41, 105.0)], Some(41)), vec![41]);
    }

    #[test]
    fn a_reset_daemon_still_delivers_what_it_raised_after_coming_back() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &at(5000, 100.0));
        assert!(s.rewind(3));
        assert_eq!(classify_frame(&mut s, &at(1, 90.0)), SubscribeAction::DuplicateSeq);
        assert_eq!(classify_frame(&mut s, &at(2, 120.0)), SubscribeAction::Deliver { seq: Some(2) });
    }

    #[test]
    fn an_idle_daemon_anchored_from_its_first_page_replays_nothing_old_after_a_restart() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let page = [at(31, 100.0), at(32, 101.0)];
        assert!(polled(&mut s, &page, Some(42)).is_empty());
        let requested = s.cursor();
        assert!(poll_into(&mut s, requested, &[], Some(40)).is_empty());
        assert_eq!(s.cursor(), Some(0));
        assert!(polled(&mut s, &page, Some(40)).is_empty());
        assert_eq!(polled(&mut s, &[at(41, 105.0)], Some(41)), vec![41]);
    }

    #[test]
    fn a_reset_with_nothing_seen_re_anchors_at_the_head_instead_of_replaying() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        s.bump_seq(42);
        assert!(!s.rewind(40));
        assert_eq!(s.cursor(), Some(40));
        assert!(polled(&mut s, &[at(31, 100.0), at(32, 101.0)], Some(40)).is_empty());
    }

    #[test]
    fn the_time_floor_lasts_one_replay_page_so_a_clock_moved_back_never_silences_live_frames() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &at(10, 500.0));
        assert!(s.rewind(3));
        assert_eq!(polled(&mut s, &[at(1, 400.0)], Some(3)), vec![1]);
        assert_eq!(classify_frame(&mut s, &at(4, 450.0)), SubscribeAction::Deliver { seq: Some(4) });
    }

    #[test]
    fn a_restart_with_a_clock_moved_back_still_delivers_what_came_after_the_reset() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[at(31, 500.0)], Some(42));
        let requested = s.cursor();
        assert!(poll_into(&mut s, requested, &[], Some(40)).is_empty());
        let page = [at(31, 500.0), at(40, 450.0), at(41, 460.0), at(42, 470.0)];
        assert_eq!(polled(&mut s, &page, Some(42)), vec![40, 41, 42]);
        assert_eq!(s.cursor(), Some(42));
    }

    #[test]
    fn a_message_raised_before_the_query_that_found_the_reset_is_delivered_when_the_clock_went_back() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &at(10, 500.0));
        assert!(s.rewind(1));
        assert_eq!(polled(&mut s, &[at(1, 400.0)], Some(1)), vec![1]);
        assert_eq!(s.cursor(), Some(1));
    }

    #[test]
    fn a_restored_page_with_no_known_frame_only_trusts_its_newest_few() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &at(900, 500.0));
        assert!(s.rewind(120));
        let page: Vec<Value> = (1..=120).map(|n| at(n, 100.0 + n as f64)).collect();
        assert_eq!(polled(&mut s, &page, Some(120)), vec![116, 117, 118, 119, 120]);
    }

    #[test]
    fn frames_that_never_reach_history_do_not_anchor_a_page() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let activity = |seq: u64| json!({"event": "activity.changed", "seq": seq, "at": 100.0 + seq as f64});
        let _ = classify_frame(&mut s, &at(10, 200.0));
        for n in 11..=20 {
            let _ = classify_frame(&mut s, &activity(n));
        }
        assert!(s.rewind(30));
        let page = [at(10, 200.0), activity(15), at(21, 150.0)];
        s.begin_page(&page);
        assert_eq!(classify_frame(&mut s, &page[0]), SubscribeAction::DuplicateSeq);
        assert_eq!(classify_frame(&mut s, &page[2]), SubscribeAction::Deliver { seq: Some(21) });
    }

    #[test]
    fn history_older_than_the_last_known_frame_stays_silent_even_when_new_ones_follow() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = polled(&mut s, &[at(31, 100.0), at(32, 101.0)], Some(42));
        let requested = s.cursor();
        assert!(poll_into(&mut s, requested, &[], Some(40)).is_empty());
        let page = [at(20, 90.0), at(31, 100.0), at(32, 101.0), at(33, 80.0)];
        assert_eq!(polled(&mut s, &page, Some(33)), vec![33]);
    }

    #[test]
    fn a_live_replay_page_gets_the_same_verdict_through_begin_page() {
        let mut s = SubscribeState::new(STATE_SEEN_CAP);
        let _ = classify_frame(&mut s, &at(31, 500.0));
        assert!(s.rewind(40));
        let page = [at(31, 500.0), at(40, 450.0)];
        s.begin_page(&page);
        assert_eq!(classify_frame(&mut s, &page[0]), SubscribeAction::DuplicateSeq);
        assert_eq!(classify_frame(&mut s, &page[1]), SubscribeAction::Deliver { seq: Some(40) });
    }
}
