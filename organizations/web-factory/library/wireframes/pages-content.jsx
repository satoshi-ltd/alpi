/* pages-content.jsx — Amenities, Dining, Gallery. Branch on styleKey. */

// ── AMENITIES ───────────────────────────────────────────────────
function Amenities({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'Dining', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={40} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 480, margin: '0 auto' }}>
          <Kicker>The experience</Kicker><H size={32} bind="page.title" style={{ margin: '10px 0' }}>Quiet luxuries</H>
          <Lines n={2} bind="page.intro" style={{ alignItems: 'center' }} /></div></Sec>
        <VGap h={42} />
        <Sec><Col gap={40}>
          {[['Spa & hammam', false], ['Sea-view pool', true], ['Private dining', false]].map(([t, rev], i) => (
            <Row key={t} gap={36} align="center" style={{ flexDirection: rev ? 'row-reverse' : 'row' }}>
              <Ph h={210} w="50%" bind={`amenities[${i}].image`} />
              <Col gap={12} style={{ flex: 1 }}><Kicker>0{i + 1}</Kicker><H size={26} bind={`amenities[${i}].title`}>{t}</H>
                <Lines n={3} bind={`amenities[${i}].description`} /></Col>
            </Row>
          ))}
        </Col></Sec>
        <VGap h={34} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 18 }}><H size={22} bind="page.title" style={{ marginBottom: 4 }}>Facilities & services</H>
          <div style={{ fontSize: 12, color: s.muted, marginBottom: 14 }}>Everything included unless noted</div>
          {[['Most popular', ['Free WiFi', '24h reception', 'Free breakfast', 'Luggage storage', 'Parking', 'Elevator']],
            ['In your room', ['TV', 'Air-con', 'Safe', 'Kettle', 'Hairdryer', 'Desk']],
            ['Good to know', ['Pets ($)', 'Laundry ($)', 'Airport shuttle ($)', 'Bar', 'Vending', 'Non-smoking']]].map(([cat, items]) => (
            <div key={cat} style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 8 }}>{cat}</div>
              <Grid cols={3} gap={8}>{items.map((it) => (
                <Row key={it} gap={7} style={{ background: s.fill, borderRadius: s.radius, padding: '8px 10px' }}>
                  <span style={{ color: s.price, fontWeight: 700 }}>✓</span><span style={{ fontSize: 11.5 }}>{it}</span></Row>))}</Grid>
            </div>
          ))}
          <Note>checklist denso · qué entra y qué no</Note></Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Facilities</Kicker><H size={26} bind="page.title" style={{ margin: '6px 0 16px' }}>Built for the working traveler</H>
          <Grid cols={3} gap={s.gap}>
            {[['Connectivity', ['Gigabit Wi-Fi', 'In-room ethernet', 'Print & scan']],
              ['Workspace', ['Business lounge', 'Co-working desks', 'Quiet booths']],
              ['Wellness', ['24h gym', 'Sauna', 'Pool']]].map(([t, items]) => (
              <Col key={t} gap={10} style={{ borderTop: `2px solid ${s.accent}`, paddingTop: 12 }}>
                <Box h={26} w={26} /><div style={{ fontWeight: 700, fontSize: 15 }}>{t}</div>
                {items.map((it) => <span key={it} style={{ fontSize: 12, color: s.muted }}>— {it}</span>)}</Col>
            ))}
          </Grid></Sec>
        <VGap h={26} />
        <Sec><div style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
          <div style={{ background: s.fill, padding: '10px 16px', fontWeight: 700, fontSize: 13 }}>Meeting rooms</div>
          {[['Boardroom', '12', 'Yes'], ['Forum', '40', 'Yes'], ['Ballroom', '120', 'On request']].map((r, i) => (
            <Row key={r[0]} style={{ padding: '11px 16px', borderTop: `1px solid ${s.line}`, fontSize: 12.5 }}>
              <span style={{ flex: 2, fontWeight: 600 }}>{r[0]}</span><span style={{ flex: 1, color: s.muted }}>Capacity {r[1]}</span>
              <span style={{ flex: 1, color: s.muted }}>AV: {r[2]}</span><Btn size="sm">Enquire</Btn></Row>
          ))}
        </div><Note style={{ marginTop: 14 }}>tabla práctica de salas</Note></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <VGap h={28} />
        <Sec><H size={28} bind="page.title" style={{ textAlign: 'center', marginBottom: 6 }}>Things to do</H>
          <div style={{ textAlign: 'center', fontSize: 13, color: s.muted, marginBottom: 22 }}>From sunrise yoga to midnight swims</div>
          <Grid cols={3} gap={s.gap}>
            {['Infinity pool', 'Spa & wellness', 'Watersports', 'Kids club', 'Beach bar', 'Sunset cruise'].map((e, i) => (
              <div key={e} style={{ position: 'relative', borderRadius: s.radius, overflow: 'hidden' }}>
                <Ph h={130} bind={`amenities[${i}].image`} />
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'flex-end', padding: 12, zIndex: 2 }}>
                  <span style={{ color: '#fff', fontFamily: s.head, fontWeight: 700, fontSize: 16, textShadow: '0 1px 6px rgba(0,0,0,.4)' }}>{e}</span></div>
              </div>
            ))}
          </Grid></Sec>
        <VGap h={28} />
      </>}

      <Footer />
    </Page>
  );
}

// ── DINING ──────────────────────────────────────────────────────
function Dining({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'Dining', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <Ph h={320} radius={0} bind="dining.image" />
        <VGap h={34} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 500, margin: '0 auto' }}>
          <Kicker>The table</Kicker><H size={32} bind="dining.title" style={{ margin: '10px 0' }}>Sea, salt and fire</H>
          <Lines n={3} bind="dining.description" style={{ alignItems: 'center' }} /></div></Sec>
        <VGap h={40} />
        <Sec><Row gap={40} align="flex-start">
          <Col gap={14} style={{ flex: 1 }}><H size={20}>A sample menu</H>
            <B b="dining.menu[]"><Col gap={8}>{['Oysters, mignonette', 'Catch of the day', 'Garden vegetables', 'Olive oil cake'].map((d) => (
              <Row key={d} justify="space-between" style={{ borderBottom: `1px solid ${s.line}`, paddingBottom: 8 }}>
                <span style={{ fontFamily: s.head, fontSize: 16 }}>{d}</span><span style={{ color: s.muted, fontSize: 13 }}>—</span></Row>))}</Col></B></Col>
          <Col gap={12} style={{ width: 220, flexShrink: 0 }}><Ph h={160} bind="dining.image2" />
            <H size={16}>Hours</H><Lines n={2} bind="dining.hours" /><Btn>Reserve a table</Btn></Col>
        </Row></Sec>
        <VGap h={32} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 18 }}><H size={22} bind="page.title" style={{ marginBottom: 12 }}>Breakfast & food</H>
          <Row gap={10} wrap style={{ marginBottom: 14 }}><Chip accent>✓ Free breakfast</Chip><Chip>7:00–10:30</Chip><Chip>Buffet</Chip><Chip>Vending 24h</Chip></Row>
          <Row gap={16} align="stretch">
            <Ph h={160} w="45%" bind="dining.image" />
            <Col gap={10} style={{ flex: 1, justifyContent: 'center' }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>What's included</div>
              <Grid cols={2} gap={8}>{['Coffee & tea', 'Pastries', 'Fruit', 'Eggs', 'Cereal', 'Juice'].map((it) => (
                <Row key={it} gap={6}><span style={{ color: s.price, fontWeight: 700 }}>✓</span><span style={{ fontSize: 12 }}>{it}</span></Row>))}</Grid>
              <Note>info simple · gratis destacado</Note></Col>
          </Row>
          <div style={{ marginTop: 14, border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 12 }}>
            <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Nearby to eat</div>
            <Grid cols={3} gap={8}>{['Café · 50m', 'Pizza · 120m', 'Market · 200m'].map((n) => (
              <Row key={n} gap={6} style={{ background: s.fill, borderRadius: s.radius, padding: 8 }}><Box h={16} w={16} radius={3} /><span style={{ fontSize: 11 }}>{n}</span></Row>))}</Grid></div></Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Dining</Kicker><H size={26} bind="page.title" style={{ margin: '6px 0 16px' }}>Eat well, on your schedule</H>
          <Grid cols={2} gap={s.gap}>
            {[['Restaurant', '6:30–22:00', 'Business breakfast buffet'], ['Lobby bar', '11:00–24:00', 'Meetings over coffee'],
              ['Grab & go', '24 hours', 'For early flights'], ['Room service', '24 hours', 'In-room dining menu']].map(([t, h, d], i) => (
              <Row key={t} gap={14} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 14 }}>
                <Ph h={70} w={84} bind={`venues[${i}].image`} />
                <Col gap={4} style={{ flex: 1, justifyContent: 'center' }}><B b={`venues[${i}].name`}><div style={{ fontWeight: 700, fontSize: 14 }}>{t}</div></B>
                  <span style={{ fontSize: 12, color: s.accent, fontWeight: 600 }}>{h}</span>
                  <span style={{ fontSize: 11.5, color: s.muted }}>{d}</span></Col></Row>
            ))}
          </Grid></Sec>
        <VGap h={26} />
      </>}

      {styleKey === 'resort' && <>
        <VGap h={26} />
        <Sec><H size={28} bind="page.title" style={{ textAlign: 'center', marginBottom: 6 }}>Restaurants & bars</H>
          <div style={{ textAlign: 'center', fontSize: 13, color: s.muted, marginBottom: 22 }}>Six venues across the island</div>
          <Grid cols={2} gap={s.gap}>
            {[['Beach Grill', 'Seafood · barefoot'], ['Sky Bar', 'Cocktails at sunset'], ['Lagoon', 'Pan-Asian fine dining'], ['Café Coral', 'All-day & breakfast']].map(([t, d], i) => (
              <Col key={t} gap={10} style={{ background: '#fff', borderRadius: s.radius, overflow: 'hidden', boxShadow: '0 6px 22px rgba(0,0,0,.06)' }}>
                <Ph h={140} radius={0} bind={`venues[${i}].image`} />
                <div style={{ padding: '0 16px 16px' }}><H size={20} bind={`venues[${i}].name`}>{t}</H>
                  <div style={{ fontSize: 12, color: s.muted, margin: '6px 0 10px' }}>{d}</div>
                  <Btn size="sm">Reserve a table</Btn></div></Col>
            ))}
          </Grid></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

// ── GALLERY ─────────────────────────────────────────────────────
function Gallery({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'Gallery', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={40} />
        <Sec><div style={{ textAlign: 'center' }}><Kicker>Gallery</Kicker><H size={32} bind="page.title" style={{ marginTop: 10 }}>A look inside</H></div></Sec>
        <VGap h={34} />
        <Sec><div style={{ columnCount: 2, columnGap: 20 }}>
          {[260, 180, 200, 240, 170, 210].map((h, i) => (
            <div key={i} style={{ breakInside: 'avoid', marginBottom: 20 }}><Ph h={h} bind={`gallery[${i}]`} />
              <div style={{ fontFamily: s.head, fontSize: 14, color: s.muted, marginTop: 6 }}>Plate {String(i + 1).padStart(2, '0')}</div></div>
          ))}
        </div></Sec>
        <VGap h={30} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 18 }}><H size={20} bind="page.title" style={{ marginBottom: 10 }}>Photos (48)</H>
          <Row gap={8} wrap style={{ marginBottom: 12 }}>{['All', 'Rooms', 'Bathroom', 'Lobby', 'Breakfast', 'Outside'].map((t, i) => (
            <Chip key={t} accent={i === 0}>{t}</Chip>))}</Row>
          <B b="gallery[]" style={{ display: 'block' }}><Grid cols={4} gap={8}>{Array.from({ length: 12 }).map((_, i) => <Ph key={i} h={90} radius={s.radius} />)}</Grid></B>
          </Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Gallery</Kicker><H size={26} bind="page.title" style={{ margin: '6px 0 16px' }}>The property</H>
          {[['Rooms', 4], ['Meeting spaces', 4], ['Restaurant & bar', 4]].map(([cat, n]) => (
            <div key={cat} style={{ marginBottom: 18 }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>{cat}</div>
              <B b="gallery[]" style={{ display: 'block' }}><Grid cols={4} gap={10}>{Array.from({ length: n }).map((_, i) => <Ph key={i} h={84} />)}</Grid></B></div>
          ))}</Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <VGap h={24} />
        <Sec><H size={28} bind="page.title" style={{ textAlign: 'center', marginBottom: 18 }}>Postcards from paradise</H>
          <B b="gallery[]" style={{ display: 'block' }}><div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gridAutoRows: '110px', gap: 12 }}>
            <Ph h="100%" radius={s.radius} style={{ gridColumn: 'span 2', gridRow: 'span 2' }} />
            <Ph h="100%" radius={s.radius} /><Ph h="100%" radius={s.radius} />
            <Ph h="100%" radius={s.radius} style={{ gridColumn: 'span 2' }} />
            <Ph h="100%" radius={s.radius} /><Ph h="100%" radius={s.radius} />
            <Ph h="100%" radius={s.radius} style={{ gridColumn: 'span 2' }} />
          </div></B></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

Object.assign(window, { Amenities, Dining, Gallery });
