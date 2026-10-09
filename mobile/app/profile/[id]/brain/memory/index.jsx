import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MEMORY_FILES } from '../../../../../../common/memoryEntries.mjs';
import { MasterDetail } from '../../../../../src/components/MasterDetail';
import { MemoryDetail } from '../../../../../src/features/brain/MemoryDetail';
import { MemoryList } from '../../../../../src/features/brain/MemoryList';
import { PanelHeader } from '../../../../../src/features/profile/PanelHeader';
import { useBack } from '../../../../../src/hooks/useBack';
import { useMasterDetail } from '../../../../../src/hooks/useMasterDetail';
import { useTheme } from '../../../../../src/theme/ThemeContext';

export default function MemoryRoute() {
  const { id } = useLocalSearchParams();
  const router = useRouter();
  const goBack = useBack();
  const { colors } = useTheme();
  const wide = useMasterDetail();
  const [picked, setPicked] = useState(null);
  const [editing, setEditing] = useState(false);
  const [savedTick, setSavedTick] = useState(0);
  const dirty = useRef(false);
  const split = wide || editing;
  const selected = picked ?? MEMORY_FILES[0].file;

  const choose = (file) => {
    if (file === selected) return;
    if (!dirty.current) {
      setPicked(file);
      return;
    }
    Alert.alert('Discard changes?', 'You have unsaved edits.', [
      { text: 'Keep editing', style: 'cancel' },
      { text: 'Discard', style: 'destructive', onPress: () => setPicked(file) },
    ]);
  };
  const open = (file) => router.push({ pathname: `/profile/${id}/brain/memory/[name]`, params: { name: file } });

  return (
    <SafeAreaView edges={['top', 'left', 'right']} style={{ flex: 1, backgroundColor: colors.bg }}>
      <PanelHeader profile={id} section="MEMORIES" count={MEMORY_FILES.length} onBack={goBack} />
      {split ? (
        <MasterDetail
          list={<MemoryList profile={id} selectedFile={selected} refreshKey={savedTick} onOpen={choose} />}
          detail={<MemoryDetail key={selected} profile={id} name={selected} embedded onDirtyChange={(value) => { dirty.current = value; setEditing(value); }} onSaved={() => setSavedTick((n) => n + 1)} />}
        />
      ) : (
        <MemoryList profile={id} refreshKey={savedTick} onOpen={open} />
      )}
    </SafeAreaView>
  );
}
