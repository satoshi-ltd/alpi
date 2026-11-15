import { Modal, Pressable, Text, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Meter } from '../../components/Meter';
import { POPOVER_EDGE, POPOVER_GAP } from '../../components/sheetStyles';
import { code } from '../../theme/code';
import { useTheme } from '../../theme/ThemeContext';
import { radii, space } from '../../theme/tokens';

export const DETAILS_W = 330;

export function detailsPosition(anchor, windowWidth) {
  const width = Math.min(DETAILS_W, windowWidth - 2 * POPOVER_EDGE);
  const centre = anchor.x + anchor.width / 2;
  const left = Math.min(Math.max(centre - width / 2, POPOVER_EDGE), windowWidth - width - POPOVER_EDGE);
  return { top: anchor.y + anchor.height + POPOVER_GAP, left, width };
}

function Row({ label, children }) {
  const { colors, fonts, fontSizes } = useTheme();
  return (
    <View style={{ minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: space.s5 }}>
      <Text style={{ fontFamily: fonts.sans.medium, fontSize: fontSizes.md, color: colors.ink2 }}>{label}</Text>
      {children}
    </View>
  );
}

export function ProfileDetails({ open, details, ...rest }) {
  return open && details ? <DetailsPopover details={details} {...rest} /> : null;
}

function DetailsPopover({ anchor, onClose, name, accent, details }) {
  const { colors, fonts, fontSizes, shadow } = useTheme();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const place = detailsPosition(anchor ?? { x: 0, y: insets.top, width, height: 0 }, width);
  const mono = { ...code(fonts, fontSizes.xs), color: colors.ink2 };
  return (
    <Modal visible transparent statusBarTranslucent animationType="none" onRequestClose={onClose} supportedOrientations={['portrait', 'landscape-left', 'landscape-right']}>
      <Pressable testID="details-backdrop" accessible={false} onPress={onClose} style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }} />
      <View
        accessibilityViewIsModal
        accessibilityLabel={`${name} details`}
        style={{
          position: 'absolute',
          ...place,
          paddingHorizontal: space.s7,
          paddingTop: space.s4,
          paddingBottom: space.s6,
          borderRadius: radii.surface,
          backgroundColor: colors.bgElev,
          ...shadow?.popover,
        }}
      >
        {details.model ? (
          <>
            <Row label="Model">
              <Text numberOfLines={1} style={{ ...mono, flexShrink: 1 }}>{details.model}</Text>
            </Row>
            {details.modelId ? (
              <Text testID="details-model-id" selectable style={{ ...code(fonts, fontSizes.xs), color: colors.ink3 }}>{details.modelId}</Text>
            ) : null}
          </>
        ) : null}
        {details.context ? (
          <Row label="Context">
            <Meter label="Context window" showPercent color={accent} {...details.context} />
          </Row>
        ) : null}
        {details.cost ? (
          <Row label="Cost today">
            <Meter label="Daily budget" showPercent color={accent} {...details.cost} />
          </Row>
        ) : null}
      </View>
    </Modal>
  );
}
