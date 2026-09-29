import { Text, View } from 'react-native';

import { Button } from '../../components/Button';
import { space } from '../../theme/tokens';
import { ThemeProvider, useTheme } from '../../theme/ThemeContext';

function CrashScreen({ error, retry }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.s10, gap: space.s5, backgroundColor: colors.bg }}>
      <Text style={{ fontFamily: fonts.sans.semibold, fontSize: fontSizes.lg, color: colors.ink, textAlign: 'center' }}>Something broke on screen</Text>
      <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3, textAlign: 'center' }}>{String(error?.message ?? error)}</Text>
      <View style={{ marginTop: space.s5 }}>
        <Button title="Reload" onPress={retry} />
      </View>
    </View>
  );
}

// expo-router mounts this for any route that throws; it renders outside the app's providers.
export function ErrorBoundary(props) {
  return (
    <ThemeProvider>
      <CrashScreen {...props} />
    </ThemeProvider>
  );
}
