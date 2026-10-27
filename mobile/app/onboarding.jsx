import { useRouter } from 'expo-router';
import { ScrollView, Text, View } from 'react-native';
import { ALPACA_FOLD, FOLD_SIZES } from '../../common/folds.mjs';
import { LINK_SOURCE_ROWS } from '../../common/onboarding.mjs';
import { space } from '../src/theme/tokens';
import { firstRun, firstRunActions, firstRunBottom, firstRunColumn, firstRunScroll, firstRunType, foldMarkStyle } from '../src/lib/firstRun';

import { Button } from '../src/components/Button';
import { Eyebrow } from '../src/components/Eyebrow';
import { Fold } from '../src/components/Fold';
import { useFirstRunLayout } from '../src/hooks/useFirstRunLayout';
import { useTheme } from '../src/theme/ThemeContext';

export default function Onboarding() {
  const router = useRouter();
  const theme = useTheme();
  const { colors } = theme;
  const { edge, insets } = useFirstRunLayout();
  const type = firstRunType(theme);

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={firstRunScroll(insets, edge)}>
        <View style={firstRunColumn}>
          <View style={foldMarkStyle}>
            <Fold fold={ALPACA_FOLD} size={FOLD_SIZES.hero} />
          </View>
          <Text accessibilityRole="header" style={type.title}>Pair with your alpi</Text>
          <Text style={type.sentence}>
            alpi runs on a computer or a server. Pair this phone once and its profiles come with you.
          </Text>
          <View style={{ marginTop: firstRun.gap, gap: space.s3 }}>
            <Eyebrow>Where do I get a link?</Eyebrow>
            <View style={{ gap: space.s3 }}>
              {LINK_SOURCE_ROWS.map(({ label, path }) => (
                <View key={label}>
                  <Text style={type.sourceLabel}>{label}</Text>
                  <Text style={type.sourcePath}>{path}</Text>
                </View>
              ))}
            </View>
          </View>
        </View>
      </ScrollView>
      <View style={firstRunBottom(insets, edge)}>
        <View style={firstRunActions}>
          <Button title="Scan QR" size="hero" fullWidth onPress={() => router.push({ pathname: '/pair', params: { mode: 'scan' } })} />
          <Button title="Paste link" variant="ghost" fullWidth onPress={() => router.push('/pair')} />
        </View>
      </View>
    </View>
  );
}
