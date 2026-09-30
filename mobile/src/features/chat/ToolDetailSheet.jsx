import { ScrollView, Text, View } from 'react-native';

import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { copyText } from '../../lib/clipboard';
import { useTheme } from '../../theme/ThemeContext';
import { lineHeights, radii, space } from '../../theme/tokens';
import { prettyArgs, toolCommand, toolOutput, toolTitle } from './toolDetail';

function Block({ label, tag, children, danger = false }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ gap: space.s3 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s3 }}>
        <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.sm, color: colors.ink3 }}>{label}</Text>
        {tag ? <Text style={{ fontFamily: fonts.mono, fontSize: fontSizes.sm, color: colors.ink3 }}>{tag}</Text> : null}
      </View>
      <View style={{ borderRadius: radii.lg, backgroundColor: colors.bgInput, paddingHorizontal: space.s6, paddingVertical: space.s5 }}>
        <Text
          selectable
          style={{
            fontFamily: fonts.mono,
            fontSize: fontSizes.md,
            lineHeight: fontSizes.md * lineHeights.relaxed,
            color: danger ? colors.dangerText : colors.ink,
          }}
        >
          {children}
        </Text>
      </View>
    </View>
  );
}

export function ToolDetailSheet({ tool, status, onClose }) {
  const { colors, fonts, fontSizes } = useTheme();
  const toast = useToast();
  const open = !!tool;
  const args = prettyArgs(tool?.args);
  const command = toolCommand(tool?.args);
  const { text: output, excerpt } = toolOutput(tool);
  const failed = status === 'error';

  const copy = async (text, what) => {
    const ok = await copyText(text);
    toast({ title: ok ? `${what} copied` : 'Copy failed', duration: 1400 });
  };

  const actions = [];
  if (output) actions.push({ id: 'copy-output', label: 'Copy output', variant: 'secondary', onPress: () => copy(output, 'Output') });
  if (command || args) {
    actions.push({
      id: 'copy-command',
      label: command ? 'Copy command' : 'Copy arguments',
      variant: 'ghost',
      onPress: () => copy(command ?? args, command ? 'Command' : 'Arguments'),
    });
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title={tool ? toolTitle(tool, status) : ''}
      primaryAction={actions.length ? actions : undefined}
    >
      <ScrollView contentContainerStyle={{ paddingHorizontal: space.s8, paddingBottom: space.s7, gap: space.s7 }}>
        {args ? <Block label="Arguments">{args}</Block> : null}
        {output ? (
          <Block label="Output" tag={excerpt ? 'excerpt' : null} danger={failed}>{output}</Block>
        ) : (
          <Text style={{ fontFamily: fonts.sans.regular, fontSize: fontSizes.md, color: colors.ink3 }}>
            {status === 'running' ? 'Still running — output appears when it finishes.' : 'No output was recorded.'}
          </Text>
        )}
      </ScrollView>
    </Sheet>
  );
}
