import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Pressable, Text, TextInput, View } from 'react-native';
import { radii, space , fontSizes} from '../../theme/tokens';

import { Button } from '../../components/Button';
import { Glyph } from '../../components/Glyph';
import { Icon } from '../../components/Icon';
import { Sheet } from '../../components/Sheet';
import { useProfileSummaries, useWorkgroups } from '../../hooks/useDaemonData';
import { useCanAdminEarly } from '../../hooks/useActiveRole';
import { profileReadyToChat } from '../../lib/profileReady';
import { accentForProfile } from '../../theme/accents';
import { useTheme } from '../../theme/ThemeContext';

export function ComposeSheet({ open, onClose }) {
  const { colors, fonts, fontSizes } = useTheme();
  const router = useRouter();
  const canAdmin = useCanAdminEarly();
  const summaries = useProfileSummaries();
  const wgs = useWorkgroups();
  const [q, setQ] = useState('');

  const items = useMemo(() => {
    const profileByName = new Map((summaries.data?.profiles ?? []).map((p) => [p.name, p]));
    const profiles = (summaries.data?.profiles ?? []).map((p) => ({
      kind: 'profile',
      id: p.name,
      name: p.name,
      label: p.name,
      accent: p.accent ?? accentForProfile(p.name),
      needsProvider: !profileReadyToChat(p),
      sub: p.identity ?? p.model ?? '',
      paused: !!p.paused,
    }));
    profiles.sort((a, b) => (a.paused ? 1 : 0) - (b.paused ? 1 : 0));
    const wg = (wgs.data?.workgroups ?? []).map((w) => {
      const hub = profileByName.get(w.hub_id);
      return {
        kind: 'workgroup',
        id: w.id,
        name: w.name || w.id,
        label: `#${w.name || w.id}`,
        accent: hub?.accent ?? accentForProfile(w.hub_id),
        sub: `hub @${w.hub_id} · ${w.members ?? 0} members`,
        paused: w.paused,
      };
    });
    return [...profiles, ...wg];
  }, [summaries.data, wgs.data]);

  // Workgroup id is a slug; name is user-typed — match against both.
  const filtered = useMemo(() => {
    const needle = q.replace(/^[@#]/, '').trim().toLowerCase();
    if (!needle) return items;
    return items.filter((it) => {
      const id = (it.id ?? '').toLowerCase();
      const name = (it.name ?? '').toLowerCase();
      return id.includes(needle) || name.includes(needle);
    });
  }, [items, q]);

  const handlePick = (it) => {
    onClose?.();
    const path = it.kind === 'workgroup' ? `/wg/${it.id}` : `/chat/${it.id}`;
    router.push(path);
  };

  const handleClose = () => {
    setQ('');
    onClose?.();
  };

  const createProfile = () => {
    onClose?.();
    router.push('/profile/new');
  };

  const createWorkgroup = () => {
    onClose?.();
    router.push('/wg/new');
  };

  return (
    <Sheet
      open={open}
      onClose={handleClose}
      title="New chat"
      subtitle="who do you want to talk to"
      primaryAction={canAdmin ? [
        { id: 'profile', label: '+ New profile', variant: 'ghost', onPress: createProfile },
        { id: 'wg', label: '+ New workgroup', variant: 'ghost', onPress: createWorkgroup },
      ] : null}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: space.s3,
          backgroundColor: colors.bgInput,
          margin: space.s7,
          paddingHorizontal: space.s6,
          height: 44,
          borderRadius: radii.lg,
          borderWidth: 0.5,
          borderColor: colors.line2,
        }}
      >
        <Icon name="search" size={18} color={colors.ink3} />
        <TextInput
          value={q}
          onChangeText={setQ}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="@alpi  ·  #architecture"
          placeholderTextColor={colors.ink4}
          style={{ flex: 1, fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink }}
        />
      </View>
      <FlatList
        data={filtered}
        keyExtractor={(it) => `${it.kind}:${it.id}`}
        keyboardShouldPersistTaps="handled"
        renderItem={({ item }) => (
          <Pressable
            onPress={() => handlePick(item)}
            android_ripple={{ color: colors.selected }}
            style={({ pressed }) => ({
              flexDirection: 'row',
              alignItems: 'center',
              gap: space.s5,
              paddingHorizontal: space.s8,
              paddingVertical: space.s5,
              opacity: item.paused ? 0.55 : 1,
              backgroundColor: pressed ? colors.selected : 'transparent',
            })}
          >
            <Glyph kind={item.kind} color={item.accent} size={36} needsProvider={item.needsProvider} />
            <View style={{ flex: 1, gap: space.s1 }}>
              <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.md, color: colors.ink }}>
                {item.kind === 'profile' ? `@${item.id}` : `#${item.name || item.id}`}
              </Text>
              {item.sub ? (
                <Text numberOfLines={1} style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.sm, color: colors.ink3 }}>
                  {item.sub}
                </Text>
              ) : null}
            </View>
          </Pressable>
        )}
        ItemSeparatorComponent={() => <View style={{ height: 0.5, backgroundColor: colors.line, marginLeft: 68 }} />}
        contentContainerStyle={{ paddingBottom: space.s9 }}
        ListEmptyComponent={() => (
          <View style={{ padding: space.s9, alignItems: 'center' }}>
            <Text style={{ color: colors.ink3, fontFamily: fonts.sans.regular, fontSize: fontSizes.md }}>
              No alpis on this daemon yet.
            </Text>
          </View>
        )}
      />
    </Sheet>
  );
}
