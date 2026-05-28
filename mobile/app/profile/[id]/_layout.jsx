import { Stack } from 'expo-router';

import { AdminGuard } from '../../../src/components/AdminGuard';

export default function ProfileSettingsLayout() {
  return (
    <AdminGuard>
      <Stack screenOptions={{ headerShown: false }} />
    </AdminGuard>
  );
}
