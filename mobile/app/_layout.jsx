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
import { useEffect, useRef } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { ToastProvider, useToast } from '../src/components/Toast';
import { EventsProvider } from '../src/hooks/useEvents';
import { useScheduleToast } from '../src/hooks/useScheduleToast';
import { AppBootstrap } from '../src/lib/AppBootstrap';
import { useEndpoint } from '../src/lib/EndpointContext';
import { EndpointProvider } from '../src/lib/EndpointProvider';
import { setAuthFailedHandler } from '../src/lib/rpc';
import { ThemeProvider, useTheme } from '../src/theme/ThemeContext';

Text.defaultProps = Text.defaultProps || {};
Text.defaultProps.style = [{ fontFamily: 'Inter_400Regular' }, Text.defaultProps.style];

// Hold native splash until fonts load so first frame isn't unstyled text.
SplashScreen.preventAutoHideAsync().catch(() => { /* */ });


// rpc.js handler is module-global; stateRef lets it read latest endpoint state without re-registering each render.
function AuthFailedBridge() {
  const router = useRouter();
  const toast = useToast();
  const { activeId, forget, connections } = useEndpoint();
  const stateRef = useRef({ activeId, forget, connections });
  useEffect(() => { stateRef.current = { activeId, forget, connections }; }, [activeId, forget, connections]);
  useEffect(() => {
    setAuthFailedHandler(async ({ endpoint } = {}) => {
      const { activeId: active, forget: forgetFn, connections: list } = stateRef.current;
      const failedId = endpoint?.id;
      if (!failedId) return;
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
  useScheduleToast();
  return (
    <>
      <StatusBar style={mode === 'dark' ? 'light' : 'dark'} />
      <AuthFailedBridge />
      <AppBootstrap>
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.bg },
            animation: 'slide_from_right',
          }}
        />
      </AppBootstrap>
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
