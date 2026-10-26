import { useLocalSearchParams } from 'expo-router';
import { useEffect } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Busy } from './Busy';
import { ScreenHeader } from './ScreenHeader';
import { useProfileSummaries } from '../hooks/useDaemonData';
import { useBack } from '../hooks/useBack';
import { useTheme } from '../theme/ThemeContext';

export function ProfileGuard({ children }) {
  const { id } = useLocalSearchParams();
  const roster = useProfileSummaries();
  const goBack = useBack();
  const { colors } = useTheme();
  const profiles = roster.data?.profiles;
  const missing =
    Array.isArray(profiles) && id !== 'default' && !profiles.some((p) => p.name === id);
  useEffect(() => {
    if (missing) goBack();
  }, [missing, goBack]);
  if (missing) return null;
  if (profiles || roster.error) return children;
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Opening profile" onBack={goBack} />
      <Busy fill label="Opening profile" />
    </SafeAreaView>
  );
}
