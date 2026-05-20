//! Pure decisions for the daemon-event subscribe loop.
//!
//! The loop in `subscribe_daemon_events` used to inline three behaviours that
//! were hard to test in isolation: seq dedupe, the subscribe-then-backfill
//! gap-fill, and "drop frame if it predates the cursor". This module exposes
//! them as pure functions over a small state struct.

use std::collections::{HashSet, VecDeque};

use serde_json::Value;

/// In-process bookkeeping per (daemon connection) for the daemon-event stream.
pub struct SubscribeState {
    /// Highest `seq` we've already delivered to the frontend.
    pub last_seq: u64,
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
        if seq > self.last_seq {
            self.last_seq = seq;
            true
        } else {
            false
        }
    }
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
/// `state` is mutated only for the live-frame path (mark_seen, bump_seq) — the
/// handshake decision is made from the current `state.last_seq` without mutation,
/// so the caller can choose to backfill (still using the pre-handshake cursor)
/// and only commit to the new anchor after the backfill walk finishes.
pub fn classify_frame(state: &mut SubscribeState, frame: &Value) -> SubscribeAction {
    let event = match frame.get("event").and_then(|v| v.as_str()) {
        Some(s) => s,
        None => return SubscribeAction::Ignore,
    };
    if event == "subscribed" {
        let anchor = frame.get("next_seq").and_then(|v| v.as_u64());
        return if state.last_seq > 0 {
            SubscribeAction::BackfillFrom(state.last_seq)
        } else if let Some(a) = anchor {
            SubscribeAction::AnchorAt(a)
        } else {
            SubscribeAction::AnchorAt(0)
        };
    }
    let seq = frame.get("seq").and_then(|v| v.as_u64());
    if let Some(seq) = seq {
        if !state.mark_seen(seq) {
            return SubscribeAction::DuplicateSeq;
        }
        state.bump_seq(seq);
    }
    SubscribeAction::Deliver { seq }
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
}
