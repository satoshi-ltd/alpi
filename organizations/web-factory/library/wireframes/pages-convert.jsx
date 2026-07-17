/* pages-convert.jsx — Offers, Booking, Location & Contact, About. */

// ── OFFERS / PACKAGES ───────────────────────────────────────────
function Offers({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Offers', 'Dining', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={40} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 460, margin: '0 auto' }}>
          <Kicker>Offers</Kicker><H size={32} bind="page.title" style={{ margin: '10px 0' }}>Reasons to linger</H>
          <Lines n={2} bind="page.intro" style={{ alignItems: 'center' }} /></div></Sec>
        <VGap h={40} />
        <Sec><Col gap={30}>
          {['Stay three, pay for two', 'A table for two & late checkout'].map((t, i) => (
            <Row key={t} gap={32} align="center" style={{ flexDirection: i % 2 ? 'row-reverse' : 'row' }}>
              <Ph h={200} w="48%" bind={`offers[${i}].image`} />
              <Col gap={12} style={{ flex: 1 }}><Kicker>Seasonal</Kicker><H size={26} bind={`offers[${i}].title`}>{t}</H>
                <Lines n={3} bind={`offers[${i}].description`} /><Btn solid={false}>Explore offer</Btn></Col></Row>
          ))}
        </Col></Sec>
        <VGap h={34} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 18 }}><H size={22} bind="page.title" style={{ marginBottom: 4 }}>Deals & offers</H>
          <div style={{ fontSize: 12, color: s.muted, marginBottom: 14 }}>Limited time — book direct & save</div>
          <Grid cols={3} gap={12}>
            {[['Early bird', '20', '30'], ['Last minute', '15', '25'], ['Weekly stay', '25', '40']].map(([t, was, off], i) => (
              <Col key={t} gap={8} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
                <div style={{ position: 'relative' }}><Ph h={88} radius={0} bind={`offers[${i}].image`} />
                  <span style={{ position: 'absolute', top: 8, left: 8, zIndex: 3, background: s.accent, color: '#fff', fontSize: 11, fontWeight: 800, padding: '3px 8px', borderRadius: s.radius }}>-{off}%</span></div>
                <div style={{ padding: '0 10px 10px' }}><B b={`offers[${i}].title`}><div style={{ fontWeight: 700, fontSize: 13 }}>{t}</div></B>
                  <Row gap={6} align="flex-end" style={{ margin: '4px 0' }}>
                    <span style={{ textDecoration: 'line-through', color: s.muted, fontSize: 12 }}>${was}0</span>
                    <span style={{ fontWeight: 800, fontSize: 17, color: s.price }}>${was}</span></Row>
                  <Btn size="sm" style={{ width: '100%' }}>Grab deal</Btn></div></Col>
            ))}
          </Grid>
          <div style={{ marginTop: 14, background: s.accentSoft, borderRadius: s.radius, padding: '12px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12.5, fontWeight: 600 }}>Use code <b style={{ color: s.accent }}>DIRECT10</b> for 10% off</span><Btn size="sm">Copy</Btn></div>
          <Note style={{ marginTop: 12 }}>descuentos, %, códigos, urgencia</Note></Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Corporate</Kicker><H size={26} bind="page.title" style={{ margin: '6px 0 16px' }}>Rates & programs</H>
          <Grid cols={3} gap={s.gap}>
            {[['Corporate rate', 'Negotiated nightly rate for your company'], ['Long stay', '7+ nights, serviced options'], ['Loyalty', 'Points, late checkout, upgrades']].map(([t, d]) => (
              <Col key={t} gap={10} style={{ borderTop: `2px solid ${s.accent}`, paddingTop: 12 }}>
                <Box h={26} w={26} /><div style={{ fontWeight: 700, fontSize: 15 }}>{t}</div>
                <span style={{ fontSize: 12, color: s.muted }}>{d}</span><Btn size="sm" solid={false} style={{ marginTop: 4 }}>Learn more</Btn></Col>
            ))}
          </Grid></Sec>
        <VGap h={24} />
        <Sec><div style={{ background: s.fill, borderRadius: s.radius, padding: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div><H size={18}>Set up a company account</H><Lines n={1} h={6} w={260} style={{ marginTop: 8 }} /></div>
          <Btn>Contact sales</Btn></div><Note style={{ marginTop: 12 }}>foco B2B, no urgencia</Note></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <VGap h={26} />
        <Sec><H size={28} bind="page.title" style={{ textAlign: 'center', marginBottom: 18 }}>Curated escapes</H>
          <Col gap={s.gap}>
            {[['Honeymoon retreat', ['Sunset cruise', 'Couples spa', 'Private dinner']], ['Family island week', ['Kids club', 'Connecting villas', 'Daily activities']]].map(([t, inc], i) => (
              <Row key={t} gap={20} align="stretch" style={{ background: '#fff', borderRadius: s.radius, overflow: 'hidden', boxShadow: '0 8px 26px rgba(0,0,0,.07)' }}>
                <Ph h={170} w="42%" radius={0} bind={`offers[${i}].image`} />
                <Col gap={10} style={{ flex: 1, justifyContent: 'center', padding: '18px 20px 18px 0' }}>
                  <H size={24} bind={`offers[${i}].title`}>{t}</H>
                  <B b={`offers[${i}].includes[]`}><Col gap={6}>{inc.map((it) => <Row key={it} gap={8}><span style={{ color: s.accent }}>✦</span><span style={{ fontSize: 12.5 }}>{it}</span></Row>)}</Col></B>
                  <Row gap={12} align="center" style={{ marginTop: 4 }}><B b={`offers[${i}].priceFrom`}><span style={{ fontWeight: 700, color: s.accent }}>from $1,890</span></B><Btn>View package</Btn></Row></Col></Row>
            ))}
          </Col></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

// ── BOOKING ─────────────────────────────────────────────────────
function Booking({ styleKey }) {
  const s = STYLES[styleKey];
  const Field = ({ label, w }) => (
    <Col gap={5} style={{ width: w, flex: w ? 'none' : 1 }}>
      <span style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: '0.03em', color: s.muted, textTransform: 'uppercase' }}>{label}</span>
      <Box h={34} br radius={s.radius} /></Col>
  );
  const Cal = () => (
    <div style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 12 }}>
      <Row justify="space-between" style={{ marginBottom: 10 }}><span style={{ fontWeight: 700, fontSize: 13 }}>‹ June ›</span></Row>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7,1fr)', gap: 5 }}>
        {Array.from({ length: 35 }).map((_, i) => (
          <div key={i} style={{ aspectRatio: '1', borderRadius: s.radius ? 6 : 0, fontSize: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: i > 9 && i < 14 ? s.accent : s.fill, color: i > 9 && i < 14 ? '#fff' : s.muted }}>{i > 3 ? i - 3 : ''}</div>))}
      </div></div>
  );
  return (
    <Page styleKey={styleKey}>
      <Nav cta={styleKey === 'budget' ? 'Book now' : 'Reserve'} utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={38} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 440, margin: '0 auto 30px' }}>
          <Kicker>Enquire</Kicker><H size={30} style={{ marginTop: 10 }}>Begin your reservation</H></div>
          <Row gap={40} align="flex-start">
            <Col gap={18} style={{ flex: 1 }}><Cal />
              <Row gap={16}><Field label="Guests" /><Field label="Room" /></Row></Col>
            <Col gap={14} style={{ width: 250, flexShrink: 0, borderLeft: `1px solid ${s.line}`, paddingLeft: 28 }}>
              <H size={18}>Your stay</H><Lines n={3} h={6} gap={9} last="50%" />
              <div style={{ borderTop: `1px solid ${s.line}`, paddingTop: 12, fontFamily: s.head, fontSize: 22 }}>$480 total</div>
              <Btn size="lg" style={{ width: '100%' }}>Send enquiry</Btn>
              <Note>flujo tranquilo tipo enquiry</Note></Col>
          </Row></Sec>
        <VGap h={30} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 16 }}><Row gap={8} style={{ marginBottom: 14, fontSize: 11, color: s.muted }}>
          <span style={{ color: s.accent, fontWeight: 700 }}>1 Room</span><span>›</span><span style={{ color: s.accent, fontWeight: 700 }}>2 Details</span><span>›</span><span>3 Confirm</span></Row>
          <Row gap={16} align="flex-start">
            <Col gap={14} style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>Guest details</div>
              <Row gap={10}><Field label="First name" /><Field label="Last name" /></Row>
              <Row gap={10}><Field label="Email" /><Field label="Phone" /></Row>
              <Field label="Special requests" />
              <div style={{ fontWeight: 700, fontSize: 14, marginTop: 6 }}>Payment</div>
              <Field label="Card number" /><Row gap={10}><Field label="Expiry" /><Field label="CVC" /></Row>
              <Row gap={8} style={{ marginTop: 4 }}><Box h={14} w={14} radius={3} /><span style={{ fontSize: 11, color: s.muted }}>Pay at hotel — free cancellation until 24h before</span></Row>
            </Col>
            <Col gap={10} style={{ width: 210, flexShrink: 0, border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 14 }}>
              <Ph h={70} radius={s.radius} /><div style={{ fontWeight: 700, fontSize: 13 }}>Double Room</div>
              <span style={{ fontSize: 11, color: s.muted }}>2 nights · 2 guests</span>
              {[['Room x2', '$148'], ['Taxes', '$18'], ['Discount', '-$14']].map(([k, v]) => (
                <Row key={k} justify="space-between" style={{ fontSize: 12 }}><span style={{ color: s.muted }}>{k}</span><span>{v}</span></Row>))}
              <Row justify="space-between" style={{ borderTop: `1px solid ${s.line}`, paddingTop: 8 }}>
                <span style={{ fontWeight: 700 }}>Total</span><span style={{ fontWeight: 800, fontSize: 18, color: s.price }}>$152</span></Row>
              <Btn style={{ width: '100%' }}>Confirm booking</Btn>
              <Note>checkout clásico + desglose</Note></Col>
          </Row></Sec>
        <VGap h={16} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Reservation</Kicker><H size={24} style={{ margin: '6px 0 16px' }}>Express booking</H>
          <Row gap={20} align="flex-start">
            <Col gap={14} style={{ flex: 1 }}>
              <Row gap={12}><Field label="Check-in" /><Field label="Check-out" /><Field label="Guests" w={90} /></Row>
              <Row gap={12}><Field label="Corporate code" /><Field label="Cost centre" /></Row>
              <div style={{ fontWeight: 700, fontSize: 13, marginTop: 6 }}>Billing & invoice</div>
              <Row gap={12}><Field label="Company" /><Field label="VAT / Tax ID" /></Row>
              <Field label="Invoice email" />
              <Row gap={8} style={{ marginTop: 2 }}><Box h={14} w={14} radius={3} /><span style={{ fontSize: 11, color: s.muted }}>Bill to company account</span></Row>
            </Col>
            <Col gap={10} style={{ width: 220, flexShrink: 0, background: s.fill, borderRadius: s.radius, padding: 16 }}>
              <div style={{ fontWeight: 700, fontSize: 14 }}>Executive Room</div>
              <Row justify="space-between" style={{ fontSize: 12 }}><span style={{ color: s.muted }}>2 nights</span><span>$370</span></Row>
              <Row justify="space-between" style={{ fontSize: 12 }}><span style={{ color: s.muted }}>Corporate −10%</span><span>−$37</span></Row>
              <Row justify="space-between" style={{ borderTop: `1px solid ${s.line}`, paddingTop: 8 }}><span style={{ fontWeight: 700 }}>Total</span><span style={{ fontWeight: 700, fontSize: 16 }}>$333</span></Row>
              <Btn style={{ width: '100%' }}>Confirm</Btn>
              <Note>código corp + facturación</Note></Col>
          </Row></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <VGap h={24} />
        <Sec><H size={26} style={{ textAlign: 'center', marginBottom: 4 }}>Plan your escape</H>
          <div style={{ textAlign: 'center', fontSize: 12, color: s.muted, marginBottom: 20 }}>Dates · villa · experiences</div>
          <Row gap={20} align="flex-start">
            <Col gap={16} style={{ flex: 1 }}>
              <BookingBar fields={['Check-in', 'Check-out', 'Guests']} cta="Find villas" />
              <div style={{ fontWeight: 700, fontSize: 14, fontFamily: s.head }}>Add experiences</div>
              <Grid cols={2} gap={12}>{[['Sunset cruise', '$120'], ['Couples spa', '$210'], ['Diving trip', '$180'], ['Private chef', '$300']].map(([t, p]) => (
                <Row key={t} justify="space-between" align="center" style={{ background: s.accentSoft, borderRadius: s.radius, padding: 12 }}>
                  <Col gap={2}><span style={{ fontWeight: 600, fontSize: 12.5 }}>{t}</span><span style={{ fontSize: 11, color: s.muted }}>{p}</span></Col>
                  <Box h={22} w={22} radius={99} br /></Row>))}</Grid>
            </Col>
            <Col gap={12} style={{ width: 220, flexShrink: 0, background: '#fff', borderRadius: s.radius, padding: 18, boxShadow: '0 8px 26px rgba(0,0,0,.08)' }}>
              <H size={16}>Your escape</H><Ph h={80} radius={s.radius} /><Lines n={2} h={6} gap={7} />
              <Row justify="space-between" style={{ borderTop: `1px solid ${s.line}`, paddingTop: 8 }}><span style={{ fontWeight: 700 }}>Total</span><span style={{ fontWeight: 700, color: s.accent }}>$2,140</span></Row>
              <Btn size="lg" style={{ width: '100%' }}>Reserve</Btn>
              <Note>reserva + upsell de experiencias</Note></Col>
          </Row></Sec>
        <VGap h={24} />
      </>}

      <Footer />
    </Page>
  );
}

// ── LOCATION & CONTACT ──────────────────────────────────────────
function Location({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'Location', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={38} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 440, margin: '0 auto' }}>
          <Kicker>Find us</Kicker><H size={32} bind="page.title" style={{ margin: '10px 0' }}>At the edge of the old town</H></div></Sec>
        <VGap h={30} />
        <Sec><Ph h={240} bind="location.map" /></Sec>
        <VGap h={26} />
        <Sec><Row gap={40} align="flex-start">
          <Col gap={10} style={{ flex: 1 }}><H size={18}>Getting here</H><Lines n={4} bind="location.directions" /></Col>
          <Col gap={10} style={{ width: 240, flexShrink: 0 }}><H size={18}>Contact</H>
            <Lines n={3} bind="contact.details" /><Btn solid={false}>Write to us</Btn></Col>
        </Row></Sec>
        <VGap h={30} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 16 }}><Ph h={220} radius={s.radius} bind="location.map" /></Sec>
        <VGap h={14} />
        <Sec><Row gap={16} align="flex-start">
          <Col gap={10} style={{ flex: 1 }}>
            <H size={16}>How to get here</H>
            {[['Airport', '25 min · €30 taxi'], ['Train station', '8 min walk'], ['Bus stop', '2 min · lines 4, 12'], ['City centre', '10 min walk']].map(([k, v]) => (
              <Row key={k} justify="space-between" style={{ background: s.fill, borderRadius: s.radius, padding: '8px 12px' }}>
                <span style={{ fontSize: 12, fontWeight: 600 }}>{k}</span><span style={{ fontSize: 12, color: s.muted }}>{v}</span></Row>))}</Col>
          <Col gap={10} style={{ width: 220, flexShrink: 0, border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 14 }}>
            <H size={14}>Contact</H><Lines n={3} h={6} gap={8} last="60%" /><Btn size="sm" style={{ width: '100%' }}>Get directions</Btn>
            <Note>distancias y transporte claros</Note></Col>
        </Row></Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Location</Kicker><H size={26} bind="page.title" style={{ margin: '6px 0 16px' }}>In the heart of the business district</H>
          <Row gap={20} align="stretch"><Ph h={220} w="52%" bind="location.map" />
            <Col gap={10} style={{ flex: 1 }}>
              <div style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
                {[['Int’l airport', '18 min'], ['Central station', '5 min'], ['Convention centre', '7 min'], ['Metro (Line 2)', '2 min']].map((r, i) => (
                  <Row key={r[0]} justify="space-between" style={{ padding: '10px 14px', borderTop: i ? `1px solid ${s.line}` : 'none', fontSize: 12.5 }}>
                    <span style={{ fontWeight: 600 }}>{r[0]}</span><span style={{ color: s.accent, fontWeight: 600 }}>{r[1]}</span></Row>))}</div>
              <Row gap={8} wrap><Chip>Valet parking</Chip><Chip>EV charging</Chip><Chip>Airport shuttle</Chip></Row></Col></Row>
          <Note style={{ marginTop: 14 }}>tabla de tiempos + transporte</Note></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <Ph h={260} radius={0} bind="location.map" />
        <VGap h={26} />
        <Sec><H size={26} bind="page.title" style={{ textAlign: 'center', marginBottom: 18 }}>Getting to the island</H>
          <Grid cols={3} gap={s.gap}>
            {[['Fly', 'To Malé, 4–11h'], ['Transfer', 'We arrange seaplane'], ['Arrive', '30 min over the reef']].map(([t, d], i) => (
              <Col key={t} gap={10} style={{ alignItems: 'center', textAlign: 'center', background: '#fff', borderRadius: s.radius, padding: 18, boxShadow: '0 6px 22px rgba(0,0,0,.06)' }}>
                <div style={{ width: 40, height: 40, borderRadius: 99, background: s.accentSoft, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: s.head, fontWeight: 700, color: s.accent }}>{i + 1}</div>
                <H size={18}>{t}</H><span style={{ fontSize: 12, color: s.muted }}>{d}</span></Col>
            ))}
          </Grid><Note style={{ marginTop: 16 }}>viaje como parte de la experiencia</Note></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

// ── ABOUT ───────────────────────────────────────────────────────
function About({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'About', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={42} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 520, margin: '0 auto' }}>
          <Kicker>Our story</Kicker><H size={36} bind="about.title" style={{ margin: '14px 0' }}>A family house, opened to the few</H>
          <Lines n={3} bind="about.body" style={{ alignItems: 'center' }} /></div></Sec>
        <VGap h={40} />
        <Sec><Ph h={260} bind="about.image" /></Sec>
        <VGap h={32} />
        <Sec><Grid cols={3} gap={28}>{['Craft', 'Quiet', 'Place'].map((v) => (
          <Col key={v} gap={10} style={{ textAlign: 'center', alignItems: 'center' }}><H size={20}>{v}</H><Lines n={2} h={6} gap={7} last="70%" style={{ alignItems: 'center' }} /></Col>))}</Grid>
          <Note style={{ marginTop: 18 }}>manifiesto editorial · valores</Note></Sec>
        <VGap h={34} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 18 }}><H size={22} bind="about.title" style={{ marginBottom: 10 }}>About this hotel</H>
          <Row gap={16} align="stretch" style={{ marginBottom: 14 }}><Ph h={150} w="45%" bind="about.image" />
            <Col gap={10} style={{ flex: 1, justifyContent: 'center' }}><Lines n={4} bind="about.body" />
              <Row gap={8} wrap><Chip accent>★ 8.9</Chip><Chip>2,481 reviews</Chip><Chip>Since 2009</Chip></Row></Col></Row>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>What guests say</div>
          <Grid cols={3} gap={10}>{['Clean & central', 'Great value', 'Friendly staff'].map((q) => (
            <Col key={q} gap={6} style={{ background: s.fill, borderRadius: s.radius, padding: 12 }}><Stars n={5} />
              <span style={{ fontSize: 12, fontWeight: 600 }}>"{q}"</span><Lines n={2} h={5} gap={5} /></Col>))}</Grid>
          <Note style={{ marginTop: 12 }}>corto + reseñas + utilitario</Note></Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>About</Kicker><H size={26} bind="about.title" style={{ margin: '6px 0 14px' }}>A dependable base for business</H>
          <Row gap={20} align="stretch"><Ph h={180} w="45%" bind="about.image" />
            <Col gap={12} style={{ flex: 1, justifyContent: 'center' }}><Lines n={4} bind="about.body" />
              <Grid cols={3} gap={10}>{[['180', 'rooms'], ['2009', 'opened'], ['4★', 'rated']].map(([n, l]) => (
                <Col key={l} gap={2}><span style={{ fontFamily: s.head, fontWeight: 700, fontSize: 22, color: s.accent }}>{n}</span><span style={{ fontSize: 11, color: s.muted }}>{l}</span></Col>))}</Grid></Col></Row></Sec>
        <VGap h={24} />
        <Sec><div style={{ fontWeight: 700, fontSize: 14, marginBottom: 10 }}>Awards & certifications</div>
          <Grid cols={4} gap={12}>{['Green Key', 'Travel Award', 'ISO 14001', 'Safe Stay'].map((a) => (
            <Col key={a} gap={8} style={{ alignItems: 'center', border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 14 }}>
              <Box h={28} w={28} radius={99} /><span style={{ fontSize: 11, fontWeight: 600, textAlign: 'center' }}>{a}</span></Col>))}</Grid>
          <Note style={{ marginTop: 14 }}>credenciales + sostenibilidad</Note></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <Ph h={300} radius={0} bind="about.image" />
        <VGap h={28} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 520, margin: '0 auto' }}>
          <Kicker>Our island</Kicker><H size={30} bind="about.title" style={{ margin: '12px 0' }}>One island, endless horizons</H>
          <Lines n={3} bind="about.body" style={{ alignItems: 'center' }} /></div></Sec>
        <VGap h={30} />
        <Sec><Grid cols={3} gap={s.gap}>{[['Sustainability', 'Solar, reef care, zero plastic'], ['Community', 'Local guides & artisans'], ['The team', '300 hosts, one family']].map(([t, d]) => (
          <Col key={t} gap={10} style={{ alignItems: 'center', textAlign: 'center', background: s.accentSoft, borderRadius: s.radius, padding: 20 }}>
            <Box h={36} w={36} radius={99} /><H size={18}>{t}</H><span style={{ fontSize: 12, color: s.muted }}>{d}</span></Col>))}</Grid>
          <Note style={{ marginTop: 16 }}>relato de marca + sostenibilidad</Note></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

Object.assign(window, { Offers, Booking, Location, About });
