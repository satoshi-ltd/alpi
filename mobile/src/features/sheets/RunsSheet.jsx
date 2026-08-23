import React, { useEffect, useState } from 'react';
import { ScrollView } from 'react-native';

import { Row, RowSeparator } from '../../components/Row';
import { Sheet } from '../../components/Sheet';
import { useRunsList } from '../../hooks/useDaemonData';
import { useEndpoint } from '../../lib/EndpointContext';
import { space } from '../../theme/tokens';

function runLabel(run) {
  return `${run.status === 'running' ? '●' : '○'} ${run.id}`;
}

function runHelper(run) {
  const stamp = run.started_at ? new Date(run.started_at * 1000).toLocaleString() : '';
  return `${run.source || 'user'} · ${run.model || '-'} · ${stamp}`;
}

export function RunsSheet({ open, onClose, profile }) {
  const { call } = useEndpoint();
  const runs = useRunsList(profile, 30, { skipWhen: !open });
  const [cancelling, setCancelling] = useState(null);
  const [actionError, setActionError] = useState('');
  const rows = runs.data?.runs ?? [];

  useEffect(() => {
    if (open) setActionError('');
  }, [open, profile]);

  const cancel = async (id) => {
    setCancelling(id);
    setActionError('');
    try {
      await call('host.run.cancel', { profile, id });
      await runs.refresh();
    } catch {
      setActionError('Could not stop run');
    } finally {
      setCancelling(null);
    }
  };

  return (
    <Sheet open={open} onClose={onClose} title="Runs" subtitle={`@${profile ?? ''} · ${rows.length} run${rows.length === 1 ? '' : 's'}`}>
      <ScrollView contentContainerStyle={{ paddingBottom: space.s7 }}>
        {actionError ? <Row label={actionError} chevron={false} /> : null}
        {rows.length === 0 ? (
          <Row label={runs.loading ? 'Loading runs…' : runs.error ? 'Runs unavailable' : 'No runs yet'} chevron={false} />
        ) : rows.map((run, index) => (
          <React.Fragment key={run.id}>
            {index > 0 ? <RowSeparator /> : null}
            <Row
              label={runLabel(run)}
              helper={runHelper(run)}
              value={run.status === 'running' ? (cancelling === run.id ? 'stopping…' : 'tap to stop') : `${run.event_count ?? 0} events`}
              onPress={run.status === 'running' && cancelling !== run.id ? () => cancel(run.id) : null}
              chevron={false}
            />
          </React.Fragment>
        ))}
      </ScrollView>
    </Sheet>
  );
}
