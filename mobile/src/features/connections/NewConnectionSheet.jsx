import { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { space } from '../../theme/tokens';

import { Field, FieldLabel } from '../../components/Field';
import { OnOff } from '../../components/OnOff';
import { PickerRow } from '../../components/PickerRow';
import { Pill } from '../../components/Pill';
import { Row } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useProfileSummaries } from '../../hooks/useDaemonData';
import { useEndpoint } from '../../lib/EndpointContext';
import { useTheme } from '../../theme/ThemeContext';

const ROLES = [
  ['member', 'Member', 'chat + settings of scoped profiles'],
  ['admin', 'Admin', 'manages profiles and connections'],
];

export function ProfilePicker({ profiles, selected, onToggle }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.s3 }}>
      {profiles.map((name) => {
        const on = selected.includes(name);
        return (
          <Pressable key={name} onPress={() => onToggle(name)} accessibilityRole="button" accessibilityLabel={`${on ? 'Exclude' : 'Include'} @${name}`}>
            <Pill tone={on ? 'on' : undefined} off={!on}>@{name}</Pill>
          </Pressable>
        );
      })}
      {!profiles.length ? (
        <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>no profiles yet</Text>
      ) : null}
    </View>
  );
}

export function NewConnectionSheet({ open, onClose, onCreated }) {
  const toast = useToast();
  const { call } = useEndpoint();
  const summaries = useProfileSummaries();
  const [label, setLabel] = useState('');
  const [role, setRole] = useState('member');
  const [scope, setScope] = useState([]);
  const [perDevice, setPerDevice] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLabel('');
    setRole('member');
    setScope([]);
    setPerDevice(false);
    setBusy(false);
  }, [open]);

  const profiles = useMemo(
    () => (summaries.data?.profiles ?? []).map((p) => p.name).filter(Boolean),
    [summaries.data],
  );

  const ready = label.trim().length > 0 && !busy;

  const create = async () => {
    if (!ready) return;
    setBusy(true);
    try {
      const payload = await call('host.connections.create', {
        label: label.trim(),
        role,
        profiles: role === 'admin' ? [] : scope,
        session_scope: role === 'member' && perDevice ? 'device' : 'connection',
      });
      toast({ title: 'Connection created', message: label.trim(), duration: 1600 });
      onClose?.();
      onCreated?.(payload);
    } catch (e) {
      toast({ title: 'Create failed', message: String(e?.data?.detail ?? e), duration: 3200 });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="New connection"
      subtitle="one identity · several devices"
      primaryAction={{ label: 'Create + pair', onPress: create, disabled: !ready, loading: busy }}
    >
      <ScrollView contentContainerStyle={{ paddingHorizontal: space.s8, paddingVertical: space.s5, gap: space.s7 }} keyboardShouldPersistTaps="handled">
        <Field label="Label" value={label} onChangeText={setLabel} placeholder="Javi, Support, agora-web…" autoCapitalize="none" autoCorrect={false} />
        <View style={{ gap: space.s2 }}>
          <FieldLabel>Role</FieldLabel>
          <View style={{ marginHorizontal: -space.s8 }}>
            {ROLES.map(([id, title, helper]) => (
              <PickerRow key={id} label={title} helper={helper} selected={role === id} onPress={() => setRole(id)} />
            ))}
          </View>
        </View>
        {role === 'member' ? (
          <>
            <View style={{ gap: space.s2 }}>
              <FieldLabel>Profiles · none selected = all</FieldLabel>
              <ProfilePicker
                profiles={profiles}
                selected={scope}
                onToggle={(name) => setScope((cur) => (cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]))}
              />
            </View>
            <Row
              label="Sessions private per device"
              helper="for one connection shared by several people"
              value={<OnOff on={perDevice} />}
              onPress={() => setPerDevice((v) => !v)}
              chevron={false}
            />
          </>
        ) : null}
      </ScrollView>
    </Sheet>
  );
}
