import { Redirect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Row, RowSeparator, SectionHeader } from '../../src/components/Row';
import { ScreenHeader } from '../../src/components/ScreenHeader';
import { useToast } from '../../src/components/Toast';
import { formatNotification } from '../../src/features/aln/kinds';
import { fireForEvent, getPermissionStatus } from '../../src/features/aln/notify';
import { SAMPLE_KINDS, sampleEvent } from '../../src/features/aln/samples';
import { loadConnections } from '../../src/lib/store';
import { useTheme } from '../../src/theme/ThemeContext';
import { radii, space } from '../../src/theme/tokens';

export default function AlnTestScreen() {
  if (!__DEV__) return <Redirect href="/" />;
  return <AlnTestScreenInner />;
}

function AlnTestScreenInner() {
  const toast = useToast();
  const { colors, fonts, fontSizes } = useTheme();
  const [perm, setPerm] = useState('undetermined');
  const [conn, setConn] = useState(null);

  const refresh = useCallback(async () => {
    setPerm(await getPermissionStatus());
    const state = await loadConnections();
    const conns = Array.isArray(state?.connections) ? state.connections : [];
    setConn(conns[0] || null);
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const onSend = async (kind) => {
    if (perm !== 'granted') {
      toast?.({
        title: 'Permission needed',
        message: 'Grant notification permission in Settings first.',
        duration: 3000,
      });
      return;
    }
    if (!conn) {
      toast?.({ title: 'No paired daemon', message: 'Pair one first.', duration: 2400 });
      return;
    }
    const ev = sampleEvent(kind, { seqOffset: Math.floor(Math.random() * 1000) });
    const fired = await fireForEvent(ev, conn, { force: true });
    toast?.({
      title: fired ? `Sent ${kind}` : 'Could not send',
      message: fired ? 'Tap the notification to test the deep link.' : 'Native scheduler rejected the dispatch.',
      duration: 2400,
    });
  };

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Test notifications" subtitle="DEV · LOCAL DISPATCH" />
      <ScrollView contentContainerStyle={{ paddingBottom: space.s11 }}>
        <View style={{ paddingHorizontal: space.s8, paddingVertical: space.s6 }}>
          <Text style={{ color: colors.ink2, fontFamily: fonts.sans.regular, fontSize: fontSizes.sm }}>
            Each button fires a sample notification with a synthetic payload. Tap the notification to verify routing behavior — the deep link will point at a sample id (no real entity), so the destination screen will load empty.
          </Text>
        </View>
        <SectionHeader>Send sample</SectionHeader>
        {SAMPLE_KINDS.map((kind, i) => {
          const preview = formatNotification(sampleEvent(kind) || {}, conn || { name: 'alpi' });
          return (
            <View key={kind}>
              {i > 0 && <RowSeparator />}
              <Row
                label={kind}
                helper={preview.body}
                onPress={() => onSend(kind)}
              />
            </View>
          );
        })}
      </ScrollView>
    </SafeAreaView>
  );
}
