/* pages-mobile.jsx — mobile Landing per style, inside a light phone shell. */

function Phone({ styleKey, children }) {
  const s = STYLES[styleKey];
  return (
    <SCtx.Provider value={s}>
      <div style={{ height: '100%', background: s.paper, fontFamily: s.body, color: s.ink,
        display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* status bar */}
        <div style={{ flexShrink: 0, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 16px', fontSize: 10, fontWeight: 700, color: s.ink }}>
          <span>9:41</span>
          <span style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
            <span style={{ width: 14, height: 8, border: `1px solid ${s.ink}`, borderRadius: 2, display: 'inline-block' }} /></span>
        </div>
        <div style={{ flex: 1, minHeight: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>{children}</div>
      </div>
    </SCtx.Provider>
  );
}

// compact mobile nav (hamburger + logo + CTA)
function MNav({ cta }) {
  const s = useS();
  return (
    <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 16px', borderBottom: `1px solid ${s.line}` }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {[0, 1, 2].map((i) => <div key={i} style={{ width: 16, height: 2, background: s.ink, borderRadius: 2 }} />)}
      </div>
      <div style={{ fontFamily: s.head, fontSize: 15, fontWeight: s.headWeight,
        letterSpacing: s.upper ? '0.18em' : 0, textTransform: s.upper ? 'uppercase' : 'none' }}>HOTEL</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <LangSelect />
        {cta ? <Btn size="sm">{cta}</Btn> : <Box h={20} w={20} radius={99} />}
      </div>
    </div>
  );
}

function LandingMobile({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Phone styleKey={styleKey}>
      {styleKey === 'boutique' && <>
        <MNav />
        <Ph h={230} radius={0} style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8, padding: 16 }}>
            <Kicker style={{ color: '#fff' }}>A house by the sea</Kicker>
            <H size={26} style={{ color: '#fff', textAlign: 'center', textShadow: '0 1px 8px rgba(0,0,0,.4)' }}>Stillness, made a place</H></div>
        </Ph>
        <div style={{ padding: '22px 18px', textAlign: 'center' }}>
          <H size={18} style={{ marginBottom: 10 }}>Twelve quiet rooms</H>
          <Lines n={3} h={6} gap={8} last="60%" style={{ alignItems: 'center' }} /></div>
        <div style={{ padding: '0 18px' }}><Ph h={150} /><H size={16} style={{ marginTop: 10 }}>The Sea Suite</H></div>
        <div style={{ marginTop: 'auto', borderTop: `1px solid ${s.line}`, padding: 14, display: 'flex', justifyContent: 'center' }}>
          <Btn style={{ width: '100%' }}>Enquire to stay</Btn></div>
      </>}

      {styleKey === 'budget' && <>
        <MNav cta="Book" />
        <Ph h={130} radius={0} style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', left: 14, bottom: 12, color: '#fff' }}>
            <H size={18} style={{ color: '#fff', textShadow: '0 1px 6px rgba(0,0,0,.4)' }}>From $59 / night</H></div>
        </Ph>
        <div style={{ padding: 12 }}><BookingBar vertical fields={['Check-in', 'Check-out', 'Guests']} cta="Search deals" /></div>
        <div style={{ padding: '0 12px' }}><Row gap={6} wrap style={{ marginBottom: 10 }}><Chip accent>★ 8.9</Chip><Chip>Free WiFi</Chip><Chip>Free cancel</Chip></Row>
          <Col gap={8}>{[['Single', '59'], ['Double', '74']].map(([r, p]) => (
            <Row key={r} gap={10} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
              <Ph h={64} w={84} radius={0} /><Col gap={2} style={{ flex: 1, justifyContent: 'center' }}><span style={{ fontWeight: 700, fontSize: 12 }}>{r} Room</span><Stars n={4} /></Col>
              <Col gap={4} style={{ justifyContent: 'center', alignItems: 'flex-end', padding: '0 10px' }}><span style={{ fontWeight: 800, color: s.price }}>${p}</span><Btn size="sm">Book</Btn></Col></Row>))}</Col></div>
      </>}

      {styleKey === 'business' && <>
        <MNav cta="Book" />
        <Ph h={120} radius={0} />
        <div style={{ padding: 16 }}><Kicker>Downtown</Kicker><H size={20} style={{ margin: '6px 0 12px' }}>Work, meet, rest</H>
          <BookingBar vertical fields={['Check-in', 'Check-out', 'Guests']} cta="Check availability" /></div>
        <div style={{ padding: '0 16px' }}><Col gap={10}>{[['Fast Wi-Fi', 'Gigabit'], ['Workspace', 'Desk + monitor'], ['Meetings', '6 rooms']].map(([t, d]) => (
          <Row key={t} gap={10} style={{ borderTop: `2px solid ${s.accent}`, paddingTop: 8 }}><Box h={22} w={22} /><Col gap={1}><span style={{ fontWeight: 700, fontSize: 12.5 }}>{t}</span><span style={{ fontSize: 11, color: s.muted }}>{d}</span></Col></Row>))}</Col></div>
      </>}

      {styleKey === 'resort' && <>
        <MNav cta="Reserve" />
        <Ph h={240} radius={0} style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, padding: 16 }}>
            <H size={26} style={{ color: '#fff', textAlign: 'center', textShadow: '0 2px 10px rgba(0,0,0,.4)' }}>Your island escape</H>
            <Btn size="md">Reserve your stay</Btn></div>
        </Ph>
        <div style={{ padding: 16 }}><H size={18} style={{ textAlign: 'center', marginBottom: 12 }}>Experiences</H>
          <Grid cols={2} gap={10}>{['Pool', 'Beach', 'Spa', 'Dining'].map((e) => (
            <div key={e} style={{ position: 'relative', borderRadius: s.radius, overflow: 'hidden' }}><Ph h={80} radius={0} />
              <span style={{ position: 'absolute', left: 8, bottom: 6, color: '#fff', fontFamily: s.head, fontWeight: 700, fontSize: 13, textShadow: '0 1px 4px rgba(0,0,0,.4)' }}>{e}</span></div>))}</Grid></div>
      </>}
    </Phone>
  );
}

Object.assign(window, { Phone, MNav, LandingMobile });
