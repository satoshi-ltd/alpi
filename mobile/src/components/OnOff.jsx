import { Pill } from './Pill';

export function OnOff({ on, onLabel = 'on', offLabel = 'off', disabled = false }) {
  const effective = !disabled && !!on;
  return (
    <Pill tone={effective ? 'on' : undefined} off={!effective}>
      ● {effective ? onLabel : offLabel}
    </Pill>
  );
}
