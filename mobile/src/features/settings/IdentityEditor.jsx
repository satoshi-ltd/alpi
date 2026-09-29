import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { Pill } from '../../components/Pill';
import { useToast } from '../../components/Toast';
import { space } from '../../theme/tokens';
import { canDraftIdentity, draftIdentity, saveIdentity } from './identityDraft';

export function IdentityEditor({ profileId, profile, call, onSaved }) {
  const toast = useToast();
  const baseline = profile?.bio ?? '';
  const [text, setText] = useState(baseline);
  const [busy, setBusy] = useState(null);

  useEffect(() => {
    setText(baseline);
  }, [baseline]);

  const dirty = text !== baseline;

  const save = async () => {
    setBusy('save');
    try {
      await saveIdentity(call, profileId, text);
      toast({ title: 'Identity saved', duration: 1400 });
      await onSaved?.();
    } catch (e) {
      toast({ title: 'Save failed', message: String(e), duration: 2400 });
    } finally {
      setBusy(null);
    }
  };

  const draft = async () => {
    if (!canDraftIdentity(profile)) {
      toast({ title: 'Set a model first', message: 'Drafting needs an LLM wired up', duration: 2400 });
      return;
    }
    setBusy('draft');
    try {
      const bio = await draftIdentity(call, profileId);
      if (bio) {
        setText(bio);
        toast({ title: 'Drafted from AGENT.md', duration: 1600 });
      } else {
        toast({ title: 'Draft empty', message: 'AGENT.md may be missing or terse', duration: 2400 });
      }
    } catch (e) {
      toast({ title: 'Draft failed', message: String(e) });
    } finally {
      setBusy(null);
    }
  };

  return (
    <View style={{ gap: space.s3 }}>
      <Field
        value={text}
        onChangeText={setText}
        multiline
        rows={3}
        placeholder="public identity — visible to peers"
        editable={busy !== 'save'}
      />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.s4 }}>
        {dirty ? (
          <>
            <Pill tone="warn">draft</Pill>
            <Button title="Discard" variant="ghost" size="sm" disabled={busy != null} onPress={() => setText(baseline)} />
            <Button title="Save" variant="primary" size="sm" loading={busy === 'save'} disabled={busy === 'draft'} onPress={save} />
          </>
        ) : null}
        <View style={{ flex: 1 }} />
        <Button title="Draft" variant="ghost" size="sm" loading={busy === 'draft'} disabled={busy === 'save'} onPress={draft} />
      </View>
    </View>
  );
}
