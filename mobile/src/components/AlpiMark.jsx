import Svg, { Path } from 'react-native-svg';

import { ALPI_PATHS, ALPI_VIEWBOX } from '../../../common/alpiMark.mjs';
import { palettes } from '../theme/tokens';

export function AlpiMark({ size = 72, color = palettes.light.ink }) {
  return (
    <Svg width={size} height={size} viewBox={ALPI_VIEWBOX}>
      {ALPI_PATHS.map((d, i) => (
        <Path key={i} d={d} fill={color} />
      ))}
    </Svg>
  );
}
