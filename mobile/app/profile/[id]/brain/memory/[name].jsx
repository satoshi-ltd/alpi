import { useLocalSearchParams } from 'expo-router';

import { MemoryDetail } from '../../../../../src/features/brain/MemoryDetail';
import { useBack } from '../../../../../src/hooks/useBack';

export default function MemoryDetailRoute() {
  const { id, name } = useLocalSearchParams();
  const goBack = useBack();
  return <MemoryDetail profile={id} name={name} onBack={goBack} />;
}
