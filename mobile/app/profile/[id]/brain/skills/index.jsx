import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MasterDetail } from '../../../../../src/components/MasterDetail';
import { NothingSelected } from '../../../../../src/components/NothingSelected';
import { SkillDetail } from '../../../../../src/features/brain/SkillDetail';
import { SkillsList, groupSkills, skillKey } from '../../../../../src/features/brain/SkillsList';
import { PanelHeader } from '../../../../../src/features/profile/PanelHeader';
import { useAttention } from '../../../../../src/hooks/useAttention';
import { useBack } from '../../../../../src/hooks/useBack';
import { useSkills } from '../../../../../src/hooks/useDaemonData';
import { useMasterDetail } from '../../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../../src/theme/ThemeContext';

export default function SkillsRoute() {
  const { id, name, category } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors } = useTheme();
  const wide = useMasterDetail();
  const skills = useSkills(id);
  const { att } = useAttention(id);
  const { rows, ordered } = groupSkills(skills.data?.skills, att);
  const [picked, setPicked] = useState(name ? { name: String(name), rawCategory: category ? String(category) : '' } : null);
  const named = picked ? ordered.find((s) => s.name === picked.name && s.rawCategory === picked.rawCategory) : null;
  const selected = named ?? ordered[0] ?? null;
  const settled = !skills.loading && !skills.error;
  const open = (s) => router.push({
    pathname: `/profile/${id}/brain/skills/[name]`,
    params: { name: s.name, path: s.path ?? '', category: s.rawCategory },
  });

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="SKILLS" count={rows.length} onBack={goBack} />
      {wide ? (
        <MasterDetail
          list={<SkillsList profile={id} selectedKey={selected ? skillKey(selected) : null} onOpen={setPicked} />}
          detail={selected ? <SkillDetail key={skillKey(selected)} profile={id} name={selected.name} category={selected.rawCategory} embedded /> : settled ? <NothingSelected>No skills installed</NothingSelected> : null}
        />
      ) : (
        <SkillsList profile={id} onOpen={open} />
      )}
    </SafeAreaView>
  );
}
