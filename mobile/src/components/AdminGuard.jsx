import { useEffect } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Busy } from './Busy';
import { ScreenHeader } from './ScreenHeader';
import { useActiveRole } from '../hooks/useActiveRole';
import { useBack } from '../hooks/useBack';
import { useTheme } from '../theme/ThemeContext';

export function AdminGuard({ children }) {
  const role = useActiveRole();
  const goBack = useBack();
  const { colors } = useTheme();
  useEffect(() => {
    if (role === 'member') goBack();
  }, [role, goBack]);
  if (role === 'admin') return children;
  if (role === 'member') return null;
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ScreenHeader title="Checking access" onBack={goBack} />
      <Busy fill label="Checking access" />
    </SafeAreaView>
  );
}
