import * as Clipboard from 'expo-clipboard';
import { useState } from 'react';

import { ActionSheet } from '../../components/ActionSheet';
import { Icon } from '../../components/Icon';
import { useToast } from '../../components/Toast';
import { useEndpoint } from '../../lib/EndpointContext';
import { shareMarkdown, sharePdf } from '../../lib/messageExport';
import { profileLabel } from '../../lib/profileName';
import { useTheme } from '../../theme/ThemeContext';
import { buildMessageActions } from './messageActions';
import { SelectTextSheet } from './SelectTextSheet';
import { useModalHandoff } from './useModalHandoff';

const ICONS = {
  copy: 'copy',
  select: 'file-text',
  download: 'download',
  pdf: 'file-text',
  edit: 'pencil',
  retry: 'refresh-cw',
  'retry-agent': 'refresh-cw',
};

export function MessageActionsSheet({ target, onClose, onRetry, onEdit }) {
  const { colors } = useTheme();
  const [selecting, setSelecting] = useState(null);
  const [armed, setArmed] = useState(false);
  const handoff = useModalHandoff();
  const selectText = (t) => handoff(() => {
    setArmed(true);
    setSelecting(t.text);
  });
  const closeSelect = () => {
    setSelecting(null);
    handoff(() => setArmed(false));
  };
  const open = !!target;
  const isAgent = target?.kind === 'agent';
  const toast = useToast();
  const { activeId, connections } = useEndpoint();
  const server = (connections ?? []).find((c) => c.id === activeId)?.name ?? '';
  const exportOf = (t) => ({ profile: t.exportProfile ? profileLabel(t.exportProfile) : '', server, at: t.exportAt ?? 0, body: t.exportBody ?? t.text });
  const exportWith = (share, failure) => (t) => handoff(async () => {
    try {
      await share(exportOf(t), t.exportAccent);
    } catch (e) {
      toast({ message: `${failure}: ${String(e?.message ?? e)}`, kind: 'danger' });
    }
  });
  const onDownload = exportWith((message) => shareMarkdown(message), 'Download failed');
  const onExportPdf = exportWith(sharePdf, 'Export failed');

  const onCopy = async (t) => {
    if (!t?.text) return;
    await Clipboard.setStringAsync(t.text);
    toast({ title: 'Copied', kind: 'success' });
  };

  const actions = buildMessageActions(target, { onCopy, onSelectText: selectText, onDownload, onExportPdf, onEdit, onRetry }).map((a) => ({
    ...a,
    icon: <Icon name={ICONS[a.id] || 'forward'} size={20} color={colors.ink2} />,
  }));

  return (
    <>
      <ActionSheet open={open} onClose={onClose} title={isAgent ? 'Agent message' : 'Your message'} actions={actions} />
      {armed ? <SelectTextSheet text={selecting} onClose={closeSelect} /> : null}
    </>
  );
}
