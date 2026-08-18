import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ScreenHeader } from '../src/components/ScreenHeader';
import { SettingsBody } from '../src/features/settings/SettingsBody';
import { useTheme } from '../src/theme/ThemeContext';

// No AdminGuard: every row is device-personal (sign out included) and fires no daemon RPC, so members belong here too.
export default function SettingsScreen() {
  const { colors } = useTheme();
  const router = useRouter();

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Settings" subtitle="THIS PHONE" onBack={() => router.back()} />
      <SettingsBody />
    </SafeAreaView>
  );
}
