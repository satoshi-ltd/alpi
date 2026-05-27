import { useEffect, useMemo, useState } from 'react';
import { Pressable, Text, TextInput, View } from 'react-native';

import { Icon } from '../../components/Icon';
import { Sheet } from '../../components/Sheet';
import { fontSizes, lineHeights, radii, space } from '../../theme/tokens';
import { useTheme } from '../../theme/ThemeContext';
import { useClarificationQueue } from './useClarificationQueue';

function modeFor(current) {
  if (!current) return 'single';
  if (current.multi) return 'multi';
  // Confirm = explicit yes/no — exactly 2 closed choices, no free-text escape.
  if (!current.allow_other && current.choices?.length === 2) return 'confirm';
  return 'single';
}

function formatRemaining(deadline, now) {
  if (!deadline) return null;
  const ms = Math.max(0, deadline - now);
  const s = Math.round(ms / 1000);
  return `${s}S`;
}

export function ClarificationSheet() {
  const { colors, fonts } = useTheme();
  const { current, busy, error, respond, cancel } = useClarificationQueue();
  const mode = modeFor(current);

  const [picked, setPicked] = useState([]);
  const [otherMode, setOtherMode] = useState(false);
  const [otherText, setOtherText] = useState('');
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setPicked([]);
    setOtherMode(false);
    setOtherText('');
  }, [current?.request_id]);

  useEffect(() => {
    if (!current?.deadline) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [current?.deadline]);

  const remaining = useMemo(
    () => (current ? formatRemaining(current.deadline, now) : null),
    [current, now],
  );

  const eyebrow = useMemo(() => {
    if (!current) return '';
    const tail = remaining ? `AUTO-CANCEL IN ${remaining}` : null;
    return ['QUESTION', tail].filter(Boolean).join(' · ');
  }, [current, remaining]);

  function toggle(label) {
    setPicked((prev) => (
      prev.includes(label) ? prev.filter((p) => p !== label) : [...prev, label]
    ));
  }

  return (
    <Sheet
      open={!!current}
      onClose={cancel}
      maxHeight="78%"
      hideHeader
    >
      {current ? (
        <View style={{ paddingHorizontal: space.s8, paddingTop: space.s5, paddingBottom: space.s8, gap: space.s6 }}>
          <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: space.s5 }}>
            <View style={{ flex: 1, gap: space.s2 }}>
              <Text
                style={{
                  fontFamily: fonts.mono,
                  fontSize: fontSizes.small,
                  color: colors.ink3,
                  letterSpacing: 0.6,
                }}
              >
                {eyebrow}
              </Text>
              <Text
                style={{
                  fontFamily: fonts.sans.bold,
                  fontSize: fontSizes.bodyLg,
                  lineHeight: fontSizes.bodyLg * lineHeights.normal,
                  color: colors.ink,
                }}
              >
                {current.question}
              </Text>
            </View>
            <Pressable disabled={busy} onPress={cancel} hitSlop={10} style={{ paddingTop: 2 }}>
              <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink3 }}>
                Cancel
              </Text>
            </Pressable>
          </View>

          {mode === 'multi' ? (
            <MultiChoices
              choices={current.choices}
              picked={picked}
              onToggle={toggle}
              busy={busy}
              colors={colors}
              fonts={fonts}
            />
          ) : mode === 'confirm' ? (
            <ConfirmChoices
              choices={current.choices}
              onPick={respond}
              busy={busy}
              colors={colors}
              fonts={fonts}
            />
          ) : (
            <SingleChoices
              choices={current.choices}
              allowOther={current.allow_other}
              otherMode={otherMode}
              setOtherMode={setOtherMode}
              otherText={otherText}
              setOtherText={setOtherText}
              onPick={respond}
              busy={busy}
              colors={colors}
              fonts={fonts}
            />
          )}

          {mode === 'multi' ? (
            <Footer
              picked={picked}
              busy={busy}
              onContinue={() => respond(JSON.stringify(picked))}
              colors={colors}
              fonts={fonts}
            />
          ) : null}

          {error ? (
            <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.small, color: colors.danger }}>
              {error}
            </Text>
          ) : null}
        </View>
      ) : null}
    </Sheet>
  );
}

function ChoiceRow({ children, onPress, disabled }) {
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => ({
        paddingVertical: space.s4,
        opacity: disabled ? 0.5 : pressed ? 0.6 : 1,
      })}
    >
      {children}
    </Pressable>
  );
}

function Radio({ filled, color }) {
  return (
    <View
      style={{
        width: 24,
        height: 24,
        borderRadius: 12,
        borderWidth: 1.5,
        borderColor: color,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {filled ? (
        <View
          style={{
            width: 12, height: 12, borderRadius: 6, backgroundColor: color,
          }}
        />
      ) : null}
    </View>
  );
}

function Checkbox({ checked, color }) {
  return (
    <View
      style={{
        width: 24,
        height: 24,
        borderRadius: 5,
        borderWidth: 1.5,
        borderColor: color,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: checked ? color : 'transparent',
      }}
    >
      {checked ? (
        <Text style={{ color: '#fff', fontSize: fontSizes.body, lineHeight: fontSizes.body }}>✓</Text>
      ) : null}
    </View>
  );
}

function OtherInline({ otherText, setOtherText, onSend, onCancel, busy, colors, fonts }) {
  const canSend = !busy && otherText.trim().length > 0;
  return (
    <View
      style={{
        marginTop: space.s2,
        borderRadius: radii.lg,
        borderWidth: 0.5,
        borderColor: colors.line,
        backgroundColor: colors.bgInput,
        paddingHorizontal: space.s5,
        paddingTop: space.s4,
        paddingBottom: space.s3,
      }}
    >
      <TextInput
        value={otherText}
        onChangeText={setOtherText}
        placeholder="Type your answer…"
        placeholderTextColor={colors.ink3}
        autoFocus
        multiline
        editable={!busy}
        style={{
          fontFamily: fonts.sans.regular,
          fontSize: fontSizes.bodyLg,
          lineHeight: fontSizes.bodyLg * lineHeights.normal,
          color: colors.ink,
          minHeight: 64,
          textAlignVertical: 'top',
          paddingVertical: 0,
        }}
      />
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: space.s5, marginTop: space.s3 }}>
        <Pressable disabled={busy} onPress={onCancel} hitSlop={6}>
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.body, color: colors.ink3 }}>
            Cancel
          </Text>
        </Pressable>
        <Pressable
          disabled={!canSend}
          onPress={onSend}
          style={{
            paddingVertical: space.s3,
            paddingHorizontal: space.s6,
            borderRadius: radii.md,
            backgroundColor: colors.ink,
            opacity: canSend ? 1 : 0.35,
          }}
        >
          <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.body, color: colors.bgPane }}>
            Send
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

function SingleChoices({
  choices, allowOther, otherMode, setOtherMode, otherText, setOtherText,
  onPick, busy, colors, fonts,
}) {
  return (
    <View>
      {choices.map((c) => (
        <ChoiceRow key={c.label} disabled={busy || otherMode} onPress={() => onPick(c.label)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s5 }}>
            <Radio filled={false} color={colors.ink3} />
            <View style={{ flex: 1 }}>
              <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.bodyLg, lineHeight: fontSizes.bodyLg * lineHeights.normal, color: colors.ink }}>
                {c.label}
              </Text>
              {c.description ? (
                <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.small, color: colors.ink3 }}>
                  {c.description}
                </Text>
              ) : null}
            </View>
          </View>
        </ChoiceRow>
      ))}
      {allowOther && !otherMode ? (
        <ChoiceRow disabled={busy} onPress={() => setOtherMode(true)}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s5 }}>
            <Icon name="edit" size={20} color={colors.ink3} />
            <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.bodyLg, lineHeight: fontSizes.bodyLg * lineHeights.normal, color: colors.ink3 }}>
              Type your own…
            </Text>
          </View>
        </ChoiceRow>
      ) : null}
      {allowOther && otherMode ? (
        <OtherInline
          otherText={otherText}
          setOtherText={setOtherText}
          onSend={() => onPick(otherText)}
          onCancel={() => { setOtherMode(false); setOtherText(''); }}
          busy={busy}
          colors={colors}
          fonts={fonts}
        />
      ) : null}
    </View>
  );
}

function MultiChoices({ choices, picked, onToggle, busy, colors, fonts }) {
  return (
    <View>
      {choices.map((c) => {
        const checked = picked.includes(c.label);
        return (
          <ChoiceRow key={c.label} disabled={busy} onPress={() => onToggle(c.label)}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s5 }}>
              <Checkbox checked={checked} color={checked ? colors.ink : colors.ink3} />
              <View style={{ flex: 1 }}>
                <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.bodyLg, lineHeight: fontSizes.bodyLg * lineHeights.normal, color: colors.ink }}>
                  {c.label}
                </Text>
                {c.description ? (
                  <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.small, color: colors.ink3 }}>
                    {c.description}
                  </Text>
                ) : null}
              </View>
            </View>
          </ChoiceRow>
        );
      })}
    </View>
  );
}

function ConfirmChoices({ choices, onPick, busy, colors, fonts }) {
  const [primary, secondary] = choices;
  return (
    <View style={{ gap: space.s4 }}>
      <Pressable
        disabled={busy}
        onPress={() => onPick(primary.label)}
        style={({ pressed }) => ({
          paddingVertical: space.s6,
          borderRadius: radii.md,
          backgroundColor: colors.ink,
          alignItems: 'center',
          opacity: busy ? 0.5 : pressed ? 0.85 : 1,
        })}
      >
        <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.bodyLg, color: colors.bgPane }}>
          {primary.label}
        </Text>
      </Pressable>
      <Pressable
        disabled={busy}
        onPress={() => onPick(secondary.label)}
        style={({ pressed }) => ({
          paddingVertical: space.s4,
          alignItems: 'center',
          opacity: busy ? 0.5 : pressed ? 0.5 : 1,
        })}
      >
        <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.bodyLg, color: colors.ink2 }}>
          {secondary.label}
        </Text>
      </Pressable>
    </View>
  );
}

function Footer({ picked, busy, onContinue, colors, fonts }) {
  const canContinue = picked.length > 0 && !busy;
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', marginTop: space.s3 }}>
      <Pressable
        disabled={!canContinue}
        onPress={onContinue}
        style={{
          paddingVertical: space.s4,
          paddingHorizontal: space.s7,
          borderRadius: radii.md,
          backgroundColor: colors.ink,
          opacity: canContinue ? 1 : 0.4,
        }}
      >
        <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.body, color: colors.bgPane }}>
          {picked.length > 0 ? `Continue · ${picked.length}` : 'Continue'}
        </Text>
      </Pressable>
    </View>
  );
}
