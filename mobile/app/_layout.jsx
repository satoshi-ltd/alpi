import {
  Geist_400Regular,
  Geist_500Medium,
  Geist_600SemiBold,
  Geist_700Bold,
} from '@expo-google-fonts/geist';
import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
} from '@expo-google-fonts/inter';
import {
  JetBrainsMono_400Regular,
  JetBrainsMono_500Medium,
  JetBrainsMono_600SemiBold,
} from '@expo-google-fonts/jetbrains-mono';
import { useFonts } from 'expo-font';
import { Stack, useRouter } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useMemo, useRef } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ToastProvider, useToast } from '../src/components/Toast';
import { ApprovalSheet } from '../src/features/approval/ApprovalSheet';
import { ClarificationSheet } from '../src/features/clarification/ClarificationSheet';
import { useNotificationTapRouter } from '../src/features/aln/deeplink';
import { PaneShell } from '../src/features/shell/PaneShell';
import { EventsProvider } from '../src/hooks/useEvents';
import { useScheduleToast } from '../src/hooks/useScheduleToast';
import { useTwoPane } from '../src/hooks/useTwoPane';
import { AppBootstrap } from '../src/lib/AppBootstrap';
import { useEndpoint } from '../src/lib/EndpointContext';
import { EndpointProvider } from '../src/lib/EndpointProvider';
import { stackAnimation } from '../src/lib/panes';
import { setAuthFailedHandler } from '../src/lib/rpc';
import { ThemeProvider, useTheme } from '../src/theme/ThemeContext';

// Hold native splash until fonts load so first frame isn't unstyled text.
SplashScreen.preventAutoHideAsync().catch(() => { /* */ });


// rpc.js handler is module-global; stateRef lets it read latest endpoint state without re-registering each render.
function AuthFailedBridge() {
  const router = useRouter();
  const toast = useToast();
  const { activeId, forget, connections, markConnectionStatus } = useEndpoint();
  const stateRef = useRef({ activeId, forget, connections, markConnectionStatus });
  useEffect(() => {
    stateRef.current = { activeId, forget, connections, markConnectionStatus };
  }, [activeId, forget, connections, markConnectionStatus]);
  useEffect(() => {
    setAuthFailedHandler(async ({ endpoint, reason } = {}) => {
      const {
        activeId: active,
        forget: forgetFn,
        connections: list,
        markConnectionStatus: markStatus,
      } = stateRef.current;
      const failedId = endpoint?.id;
      if (!failedId) return;
      if (reason === 'connection-disabled') {
        markStatus?.(failedId, 'disabled');
        toast({
          title: 'Connection disabled',
          message: 'Ask an admin to enable it in Settings → Connections',
          duration: 3200,
        });
        return;
      }
      try { await forgetFn?.(failedId); } catch { /* */ }
      const wasActive = active === failedId;
      const remaining = (list ?? []).filter((c) => c.id !== failedId);
      toast({
        title: wasActive ? 'Daemon revoked this phone' : `Forgot ${endpoint?.name ?? 'stale daemon'}`,
        message: wasActive
          ? (remaining.length ? 'Switched to another paired daemon' : 'Pair again to keep going')
          : 'Auth token rejected — removed from list',
        duration: 3200,
      });
      if (wasActive && remaining.length === 0) {
        router.replace('/pair');
      }
    });
    return () => setAuthFailedHandler(null);
  }, [router, toast]);
  return null;
}

function Routes() {
  const { mode, colors } = useTheme();
  const twoPane = useTwoPane();
  useScheduleToast();
  useNotificationTapRouter();
  // Never key or wrap <Stack> — a remount drops navigation state.
  const screenOptions = useMemo(() => ({
    headerShown: false,
    contentStyle: { backgroundColor: colors.bg },
    animation: stackAnimation(twoPane),
    freezeOnBlur: true,
  }), [colors.bg, twoPane]);
  return (
    <>
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
      <AuthFailedBridge />
      <AppBootstrap>
        <PaneShell>
          <Stack screenOptions={screenOptions} />
        </PaneShell>
      </AppBootstrap>
      <ApprovalSheet />
      <ClarificationSheet />
    </>
  );
}

function Boot() {
  const { colors } = useTheme();
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
      <ActivityIndicator color={colors.ink2} />
    </View>
  );
}

export default function RootLayout() {
  const [fontsReady] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    Geist_400Regular,
    Geist_500Medium,
    Geist_600SemiBold,
    Geist_700Bold,
    JetBrainsMono_400Regular,
    JetBrainsMono_500Medium,
    JetBrainsMono_600SemiBold,
  });

  useEffect(() => {
    if (fontsReady) SplashScreen.hideAsync().catch(() => { /* */ });
  }, [fontsReady]);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <ThemeProvider>
          <EndpointProvider>
            <EventsProvider>
              <ToastProvider>{fontsReady ? <Routes /> : <Boot />}</ToastProvider>
            </EventsProvider>
          </EndpointProvider>
        </ThemeProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
