import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ToolDetail } from '../../../../../src/features/brain/ToolDetail';
import { useBack } from '../../../../../src/hooks/useBack';
import { useMasterDetail } from '../../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../../src/theme/ThemeContext';

export default function ToolRoute() {
  const { id, name } = useLocalSearchParams();
  const goBack = useBack();
  const router = useRouter();
  const wide = useMasterDetail();
  const { colors } = useTheme();
  useEffect(() => {
    if (wide) router.replace({ pathname: `/profile/${id}/brain/tools`, params: { name: String(name) } });
  }, [wide, id, name, router]);
  if (wide) return null;
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <ToolDetail profile={id} name={name} onBack={goBack} />
    </SafeAreaView>
  );
}
