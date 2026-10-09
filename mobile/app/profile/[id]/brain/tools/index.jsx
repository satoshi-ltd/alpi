import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MasterDetail } from '../../../../../src/components/MasterDetail';
import { NothingSelected } from '../../../../../src/components/NothingSelected';
import { ToolDetail } from '../../../../../src/features/brain/ToolDetail';
import { ToolsList, groupTools } from '../../../../../src/features/brain/ToolsList';
import { PanelHeader } from '../../../../../src/features/profile/PanelHeader';
import { useBack } from '../../../../../src/hooks/useBack';
import { useTools } from '../../../../../src/hooks/useDaemonData';
import { useMasterDetail } from '../../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../../src/theme/ThemeContext';

export default function ToolsRoute() {
  const { id, name } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors } = useTheme();
  const wide = useMasterDetail();
  const tools = useTools(id);
  const { rows, ordered } = groupTools(tools.data?.tools);
  const [picked, setPicked] = useState(name ? String(name) : null);
  const selected = ordered.some((t) => t.name === picked) ? picked : ordered[0]?.name ?? null;
  const settled = !tools.loading && !tools.error;
  const open = (t) => router.push({ pathname: `/profile/${id}/brain/tools/[name]`, params: { name: t.name } });

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="TOOLS" count={rows.length} onBack={goBack} />
      {wide ? (
        <MasterDetail
          list={<ToolsList profile={id} selectedName={selected} onOpen={(t) => setPicked(t.name)} />}
          detail={selected ? <ToolDetail key={selected} profile={id} name={selected} embedded /> : settled ? <NothingSelected>No tools registered</NothingSelected> : null}
        />
      ) : (
        <ToolsList profile={id} onOpen={open} />
      )}
    </SafeAreaView>
  );
}
