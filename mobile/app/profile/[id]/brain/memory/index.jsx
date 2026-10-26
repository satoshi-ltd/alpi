import { useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';

import { MEMORY_FILES } from '../../../../../../common/memoryEntries.mjs';
import { useConfirm } from '../../../../../src/components/ConfirmProvider';
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
  const confirm = useConfirm();
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
    confirm({
      title: 'Discard changes?',
      body: 'You have unsaved edits.',
      confirmLabel: 'Discard',
      cancelLabel: 'Keep editing',
    }).then((discard) => { if (discard) setPicked(file); });
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
