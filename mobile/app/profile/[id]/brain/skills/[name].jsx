import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { SkillDetail } from '../../../../../src/features/brain/SkillDetail';
import { useBack } from '../../../../../src/hooks/useBack';
import { useMasterDetail } from '../../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../../src/theme/ThemeContext';

export default function SkillRoute() {
  const { id, name, category } = useLocalSearchParams();
  const goBack = useBack();
  const router = useRouter();
  const wide = useMasterDetail();
  const { colors } = useTheme();
  useEffect(() => {
    if (wide) router.replace({ pathname: `/profile/${id}/brain/skills`, params: { name: String(name), category: category ? String(category) : '' } });
  }, [wide, id, name, category, router]);
  if (wide) return null;
  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <SkillDetail profile={id} name={name} category={category} onBack={goBack} />
    </SafeAreaView>
  );
}
