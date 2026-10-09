import { useEffect, useRef, useState } from 'react';
import { Share, Text, View } from 'react-native';
import { radii, space } from '../../theme/tokens';

import { PickerRow } from '../../components/PickerRow';
import { Pill } from '../../components/Pill';
import { Row, RowSeparator } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { copyText } from '../../lib/clipboard';
import { useEndpoint } from '../../lib/EndpointContext';
import { useTheme } from '../../theme/ThemeContext';
import { pairingLink } from './format';
import { EMPTY } from '../../../../common/emptyCopy.mjs';

const POLL_MS = 2500;

function endpointsOf(payload) {
  if (payload?.endpoints?.length) return payload.endpoints;
  return payload?.url ? [{ url: payload.url, label: 'default' }] : [];
}

export const SPENT_LINK_NOTE = 'This link has been used or has expired. Generate a new one to pair another device.';

export function liveLink(status, link) {
  return status === 'pending' ? link : '';
}

export function PairingSheet({ open, onClose, payload, onSettled }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const { call } = useEndpoint();
  const endpoints = endpointsOf(payload);
  const [endpointUrl, setEndpointUrl] = useState(endpoints[0]?.url ?? '');
  const [status, setStatus] = useState('pending');
  const settledRef = useRef(onSettled);
  useEffect(() => {
    settledRef.current = onSettled;
  });

  useEffect(() => {
    setEndpointUrl(endpointsOf(payload)[0]?.url ?? '');
    setStatus(payload?.pairing_token ? payload.pairing_status || 'pending' : 'consumed');
  }, [payload?.pairing_id, payload?.pairing_token, payload?.pairing_status]);

  useEffect(() => {
    if (!open || status !== 'pending' || !payload?.pairing_id) return undefined;
    const timer = setInterval(async () => {
      try {
        const next = await call('host.connections.pairing_status', {
          connection_id: payload.connection_id,
          pairing_id: payload.pairing_id,
        });
        if (next?.status && next.status !== 'pending') {
          setStatus(next.status);
          settledRef.current?.(next.status);
        }
      } catch {
        return;
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [open, status, payload?.pairing_id, payload?.connection_id, call]);

  const link = liveLink(status, pairingLink(payload, endpointUrl));

  const close = async () => {
    if (status === 'pending' && payload?.pairing_id) {
      try {
        await call('host.connections.cancel_pairing', {
          connection_id: payload.connection_id,
          pairing_id: payload.pairing_id,
        });
      } catch {
        // the grant expires on its own after ten minutes
      }
      settledRef.current?.('cancelled');
    }
    onClose?.();
  };

  const copy = async () => {
    const ok = await copyText(link);
    toast({ title: ok ? 'Pairing link copied' : 'Copy failed', duration: 1400 });
  };

  const share = async () => {
    try {
      await Share.share({ message: link });
    } catch {
      toast({ title: 'Share failed', duration: 1400 });
    }
  };

  const tone = status === 'consumed' ? 'on' : status === 'pending' ? 'warn' : 'err';

  return (
    <Sheet
      open={open}
      onClose={close}
      dismissible={status !== 'pending'}
      title="Pair a device"
      subtitle={payload?.label ? `${payload.label} · ${payload.role ?? 'member'}` : undefined}
      primaryAction={
        status === 'pending'
          ? { label: 'Copy pairing link', onPress: copy }
          : { label: 'Done', onPress: onClose }
      }
    >
      <View style={{ paddingHorizontal: space.s8, paddingTop: space.s5, gap: space.s3 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
          <Pill tone={tone}>{status}</Pill>
          <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.xs, color: colors.ink3 }}>
            {status === 'pending' ? 'one use · expires in 10 minutes' : status === 'consumed' ? 'the device holds its token now' : 'generate a new link'}
          </Text>
        </View>
        <Text
          selectable
          style={{
            fontFamily: fonts.mono,
            fontSize: fontSizes.sm,
            color: colors.ink2,
            padding: space.s5,
            borderRadius: radii.xs,
            backgroundColor: colors.bgInput,
            borderWidth: 0.5,
            borderColor: colors.line2,
          }}
        >
          {link || (status === 'pending' ? `${EMPTY.endpoint.title}. ${EMPTY.endpoint.hint}` : SPENT_LINK_NOTE)}
        </Text>
      </View>
      {endpoints.length > 1 ? (
        <View style={{ marginTop: space.s5 }}>
          {endpoints.map((e, i) => (
            <View key={e.url}>
              {i > 0 ? <RowSeparator /> : null}
              <PickerRow
                label={e.label || e.url}
                helper={e.label ? e.url : undefined}
                selected={endpointUrl === e.url}
                onPress={() => setEndpointUrl(e.url)}
              />
            </View>
          ))}
        </View>
      ) : null}
      <View style={{ marginTop: space.s5 }}>
        <Row label="Share link" helper="AirDrop, Messages, email…" onPress={link ? share : undefined} />
      </View>
    </Sheet>
  );
}
