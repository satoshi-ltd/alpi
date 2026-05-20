import { useEffect, useState } from 'react';
import { ScrollView } from 'react-native';
import { space } from '../../theme/tokens';

import { Field } from '../../components/Field';
import { Sheet } from '../../components/Sheet';
import { useToast } from '../../components/Toast';
import { useEndpoint } from '../../lib/EndpointContext';

export function EditBudgetSheet({ open, onClose, workgroup, onSaved }) {
  const toast = useToast();
  const { call } = useEndpoint();
  const [value, setValue] = useState('25');

  // Daemon device_state::_hub_workgroups returns flat `budget_usd`, not nested `budget.cap`.
  useEffect(() => {
    if (open && workgroup?.budget_usd != null) setValue(String(workgroup.budget_usd));
  }, [open, workgroup?.budget_usd]);

  const save = async () => {
    if (!workgroup) return;
    try {
      await call('host.workgroup.update', {
        profile: workgroup.profile,
        wg_id: workgroup.id,
        budget_usd: Number(value),
      });
      toast({ title: 'Cap saved', duration: 1400 });
      onSaved?.();
      onClose?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    }
  };

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Budget cap"
      subtitle={`#${workgroup?.id ?? ''} · WEEKLY USD`}
      primaryAction={{ label: 'Save', onPress: save }}
    >
      <ScrollView contentContainerStyle={{ padding: space.s8 }} keyboardShouldPersistTaps="handled">
        <Field
          label="USD per week"
          value={value}
          onChangeText={setValue}
          keyboardType="decimal-pad"
          mono
          helper="Hub stops firing new tasks when the cap is hit."
        />
      </ScrollView>
    </Sheet>
  );
}
