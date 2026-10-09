import { useLocalSearchParams } from 'expo-router';

import { NotificationPage } from '../../../src/features/notifications/NotificationPage';

export default function OutputDetailScreen() {
  const { profile, id, connectionId } = useLocalSearchParams();
  return <NotificationPage key={`${connectionId ?? ''}:${profile}:${id}`} profile={profile} id={id} connectionId={connectionId} />;
}
