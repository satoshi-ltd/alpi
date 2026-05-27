// Gmail OAuth (host.gateway.gmail_authorize) is desktop-only — streaming + in-app browser hand-off.

import { useLocalSearchParams, useRouter } from 'expo-router';
import { ActivityIndicator, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Pill } from '../../../../src/components/Pill';
import { Row, RowSeparator } from '../../../../src/components/Row';
import { ScreenHeader } from '../../../../src/components/ScreenHeader';
import { useGatewayStatus } from '../../../../src/hooks/useDaemonData';
import { GATEWAY_DESC, GATEWAY_LABELS, GATEWAY_ORDER } from '../../../../src/lib/gateways';
import { space } from '../../../../src/theme/tokens';
import { useTheme } from '../../../../src/theme/ThemeContext';

export default function GatewaysList() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const { colors } = useTheme();
  const gateways = useGatewayStatus(id);

  const statusOf = (name) =>
    (gateways.data?.gateways ?? []).find((g) => g.name === name)?.configured ?? false;

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader
        title="Gateways"
        subtitle={`@${id} · INBOUND CHANNELS`}
        onBack={() => router.back()}
      />
      <ScrollView>
        {gateways.loading && !gateways.data ? (
          <View style={{ padding: space.s11, alignItems: 'center' }}>
            <ActivityIndicator color={colors.ink3} />
          </View>
        ) : (
          GATEWAY_ORDER.map((name, i) => {
            const configured = statusOf(name);
            return (
              <View key={name}>
                {i > 0 ? <RowSeparator /> : null}
                <Row
                  label={GATEWAY_LABELS[name]}
                  helper={GATEWAY_DESC[name]}
                  value={configured ? <Pill tone="on">on</Pill> : <Pill off>off</Pill>}
                  onPress={() => router.push(`/profile/${id}/gateways/${name}`)}
                />
              </View>
            );
          })
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
