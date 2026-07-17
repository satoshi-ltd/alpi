/* pages-core.jsx — Landing, Rooms (list), Room detail. One function per page,
   branching structurally on styleKey. Desktop compositions (width 900). */

// ── Shared landing sections ─────────────────────────────────────
// Token-driven, so each renders in its style's voice automatically.
function DiningTeaser({ reverse }) {
  const s = useS();
  return (
    <Sec><Row gap={36} align="center" style={{ flexDirection: reverse ? 'row-reverse' : 'row' }}>
      <Ph h={240} w="48%" bind="dining.image" />
      <Col gap={14} style={{ flex: 1 }}>
        <Kicker>Dining</Kicker>
        <H size={26} bind="dining.title">Sea, salt and fire</H>
        <Lines n={3} bind="dining.description" />
        <Btn solid={false}>Explore dining</Btn>
      </Col>
    </Row></Sec>
  );
}

function GalleryStrip({ cols = 4 }) {
  const s = useS();
  return (
    <Sec>
      <Row justify="space-between" align="flex-end" style={{ marginBottom: 14 }}>
        <div><Kicker>Gallery</Kicker><H size={24} style={{ marginTop: 8 }}>Explore the hotel</H></div>
        <span style={{ fontSize: 12, color: s.accent, fontWeight: 600 }}>View gallery →</span>
      </Row>
      <Grid cols={cols} gap={s.gap < 18 ? 10 : 14}>
        {Array.from({ length: cols }).map((_, i) => <Ph key={i} h={130} bind={`gallery[${i}]`} />)}
      </Grid>
    </Sec>
  );
}

function Reviews({ center = true }) {
  const s = useS();
  const data = [
    ['A quiet, faultless stay — we are already planning to return.', 'Marta · Madrid'],
    ['Beautiful rooms and the warmest team we have met in years.', 'James · London'],
    ['Effortless from booking to breakfast. Exactly what we needed.', 'Sofia · Milan'],
  ];
  return (
    <Sec>
      <div style={{ textAlign: center ? 'center' : 'left', marginBottom: 18 }}>
        <Kicker>Reviews</Kicker><H size={26} style={{ marginTop: 8 }}>What our guests say</H>
      </div>
      <Grid cols={3} gap={s.gap}>
        {data.map(([q, a], i) => (
          <Col key={i} gap={10} style={{ borderRadius: s.radius, padding: s.key === 'boutique' ? 22 : 16,
            background: s.key === 'boutique' ? 'transparent' : s.fill,
            border: s.key === 'boutique' ? `1px solid ${s.line}` : 'none' }}>
            <Stars n={5} />
            <P bind={`testimonials[${i}].quote`} style={{ fontFamily: s.head, fontSize: 16, color: s.ink, lineHeight: 1.4 }}>“{q}”</P>
            <B b={`testimonials[${i}].author`}><span style={{ fontSize: 12, color: s.muted, fontWeight: 600 }}>{a}</span></B>
          </Col>
        ))}
      </Grid>
    </Sec>
  );
}

function LocationTeaser({ boxed }) {
  const s = useS();
  return (
    <Sec><Row gap={28} align="stretch" style={{ background: boxed ? s.fill : 'transparent',
      borderRadius: s.radius, padding: boxed ? 16 : 0 }}>
      <Ph h={210} w="48%" bind="location.map" />
      <Col gap={12} style={{ flex: 1, justifyContent: 'center' }}>
        <Kicker>Location</Kicker>
        <H size={24}>Perfectly placed</H>
        <Lines n={3} bind="location.directions" />
        <Row gap={8} wrap><Chip>Airport 20 min</Chip><Chip>Beach 5 min</Chip><Chip>Old town 10 min</Chip></Row>
        <Btn solid={false}>Get directions</Btn>
      </Col>
    </Row></Sec>
  );
}

function Newsletter() {
  const s = useS();
  const r = s.btnRadius >= 900 ? 999 : s.radius;
  return (
    <Sec><div style={{ background: s.accent, borderRadius: s.radius, padding: '26px 30px', display: 'flex',
      alignItems: 'center', justifyContent: 'space-between', gap: 24, flexWrap: 'wrap' }}>
      <div style={{ flex: '1 1 260px' }}>
        <div style={{ fontFamily: s.head, fontWeight: s.headWeight, fontSize: 22, color: '#fff' }}>Join our newsletter</div>
        <div style={{ fontSize: 13, color: '#fff', opacity: 0.85, marginTop: 4 }}>Offers, stories and seasonal escapes, straight to your inbox.</div>
      </div>
      <div style={{ display: 'flex', gap: 10, flex: '0 1 360px' }}>
        <div style={{ flex: 1, height: 44, background: '#fff', borderRadius: r, display: 'flex',
          alignItems: 'center', padding: '0 14px', fontSize: 12.5, color: s.muted }}>your@email.com</div>
        <span style={{ display: 'inline-flex', alignItems: 'center', padding: '0 22px', background: '#fff',
          color: s.accent, fontWeight: 700, fontSize: 13, borderRadius: r, whiteSpace: 'nowrap' }}>Subscribe</span>
      </div>
    </div></Sec>
  );
}

// ── LANDING ─────────────────────────────────────────────────────
function Landing({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      {styleKey === 'boutique' && <>
        <Nav links={['Stay', 'Dining', 'Spa', 'Journal', 'Contact']} />
        <Ph h={350} radius={0} bind="hero.image" style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 14 }}>
            <Kicker bind="hero.eyebrow" style={{ color: '#fff' }}>A house by the sea</Kicker>
            <H size={44} bind="hero.title" style={{ textAlign: 'center', color: '#fff' }} w={520}>Where stillness becomes a place</H>
          </div>
        </Ph>
        <Sec style={{ marginTop: -34, position: 'relative', zIndex: 2 }}>
          <BookingBar fields={['Check-in', 'Check-out', 'Guests', 'Rooms']} cta="Check availability" bind="bookingWidget (plugin)" />
        </Sec>
        <VGap h={40} />
        <Sec><div style={{ maxWidth: 520, margin: '0 auto', textAlign: 'center' }}>
          <H size={24} bind="page.intro.title" style={{ marginBottom: 14 }}>Twelve rooms. One quiet promise.</H>
          <Lines n={3} bind="page.intro.body" style={{ alignItems: 'center' }} />
        </div></Sec>
        <VGap h={46} />
        <Sec><Row gap={36} align="stretch">
          <Ph h={260} w="52%" bind="about.image" />
          <Col gap={16} style={{ flex: 1, justifyContent: 'center' }}>
            <Kicker bind="about.eyebrow">The setting</Kicker>
            <H size={28} bind="about.title">An old villa, gently restored</H>
            <Lines n={4} bind="about.body" />
          </Col>
        </Row></Sec>
        <VGap h={46} />
        <Sec><Kicker style={{ marginBottom: 16 }}>The rooms</Kicker>
          <Grid cols={2} gap={24}>
            {['Garden Room', 'Sea Suite'].map((r, i) => (
              <Col key={r} gap={10}><Ph h={220} bind={`rooms[${i}].image`} /><H size={20} bind={`rooms[${i}].name`}>{r}</H><Lines n={1} /></Col>
            ))}
          </Grid>
        </Sec>
        <VGap h={46} />
        <DiningTeaser />
        <VGap h={46} />
        <GalleryStrip cols={4} />
        <VGap h={46} />
        <Reviews />
        <VGap h={46} />
        <LocationTeaser />
        <VGap h={44} />
        <Sec><div style={{ borderTop: `1px solid ${s.line}`, borderBottom: `1px solid ${s.line}`,
          padding: '22px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <H size={22}>Reserve your stay</H>
          <Row gap={14}><span style={{ fontSize: 12, color: s.muted }}>Dates · Guests</span><Btn>Enquire</Btn></Row>
        </div></Sec>
        <VGap h={36} />
        <Newsletter />
        <VGap h={40} />
      </>}

      {styleKey === 'budget' && <>
        <Nav links={['Rooms', 'Deals', 'Location', 'FAQ']} cta="Book now" />
        <Ph h={210} radius={0} bind="hero.image" style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', left: s.pad, top: 26, color: '#fff', zIndex: 2 }}>
            <H size={30} bind="hero.title" style={{ color: '#fff', textShadow: '0 1px 6px rgba(0,0,0,.4)' }}>Rooms from $59 / night</H>
            <div style={{ fontSize: 13, marginTop: 4, textShadow: '0 1px 4px rgba(0,0,0,.4)' }}>Free cancellation · No prepay</div>
          </div>
        </Ph>
        <Sec style={{ marginTop: -28, position: 'relative', zIndex: 2 }}>
          <BookingBar fields={['Check-in', 'Check-out', 'Guests', 'Rooms']} cta="Search deals" bind="bookingWidget (plugin)" />
        </Sec>
        <VGap h={16} />
        <Sec><Row gap={10} wrap>
          <Chip accent>★ 8.9 Very good</Chip><Chip>2,481 reviews</Chip><Chip>✓ Free WiFi</Chip>
          <Chip>✓ Free cancellation</Chip><Chip>✓ Pay at hotel</Chip>
        </Row></Sec>
        <VGap h={18} />
        <Sec><Row justify="space-between" style={{ marginBottom: 12 }}>
          <H size={18}>Popular rooms</H><span style={{ fontSize: 12, color: s.accent, fontWeight: 600 }}>See all 14 →</span>
        </Row>
        <Grid cols={3} gap={12}>
          {[['Single', '59'], ['Double', '74'], ['Family', '98']].map(([r, p], i) => (
            <Col key={r} gap={8} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
              <Ph h={96} radius={0} bind={`rooms[${i}].image`} />
              <div style={{ padding: '0 10px 10px' }}>
                <B b={`rooms[${i}].name`}><div style={{ fontWeight: 700, fontSize: 13 }}>{r} Room</div></B>
                <Stars n={4} />
                <Row justify="space-between" align="flex-end" style={{ marginTop: 6 }}>
                  <span style={{ fontSize: 11, color: s.muted }}>from</span>
                  <B b={`rooms[${i}].priceFrom`}><span style={{ fontWeight: 800, fontSize: 17, color: s.price }}>${p}</span></B>
                </Row>
                <Btn size="sm" style={{ width: '100%', marginTop: 8 }}>Reserve</Btn>
              </div>
            </Col>
          ))}
        </Grid></Sec>
        <VGap h={18} />
        <Sec><Grid cols={4} gap={10}>
          {['Free WiFi', '24h desk', 'Breakfast', 'Parking'].map((u) => (
            <Col key={u} gap={6} style={{ alignItems: 'center', background: s.fill, borderRadius: s.radius, padding: 12 }}>
              <Box h={22} w={22} radius={99} /><span style={{ fontSize: 11, fontWeight: 600 }}>{u}</span>
            </Col>
          ))}
        </Grid></Sec>
        <VGap h={20} />
        <Reviews />
        <VGap h={20} />
        <LocationTeaser boxed />
        <VGap h={20} />
        <GalleryStrip cols={6} />
        <VGap h={20} />
        <Newsletter />
        <VGap h={22} />
      </>}

      {styleKey === 'business' && <>
        <Nav links={['Rooms', 'Meetings', 'Dining', 'Location']} cta="Book" utility />
        <Sec style={{ marginTop: 22 }}><Row gap={24} align="stretch">
          <Col gap={16} style={{ flex: 1.1, justifyContent: 'center' }}>
            <Kicker bind="hero.eyebrow">Downtown · Financial district</Kicker>
            <H size={34} bind="hero.title">Work, meet and rest in one address</H>
            <Lines n={2} bind="hero.subtitle" />
            <BookingBar vertical fields={['Check-in', 'Check-out', 'Guests', 'Rooms']} cta="Check availability"
              bind="bookingWidget (plugin)" style={{ marginTop: 6 }} />
          </Col>
          <Ph h={300} w="46%" bind="hero.image" />
        </Row></Sec>
        <VGap h={30} />
        <Sec><Grid cols={3} gap={18}>
          {[['Fast Wi-Fi', 'Gigabit in every room'], ['Workspace', 'Ergonomic desk + monitor'], ['Meetings', '6 rooms up to 120']].map(([t, d]) => (
            <Col key={t} gap={8} style={{ borderTop: `2px solid ${s.accent}`, paddingTop: 12 }}>
              <Box h={26} w={26} /><div style={{ fontWeight: 700, fontSize: 14 }}>{t}</div>
              <span style={{ fontSize: 12, color: s.muted }}>{d}</span>
            </Col>
          ))}
        </Grid></Sec>
        <VGap h={26} />
        <Sec><div style={{ background: s.accent, borderRadius: s.radius, padding: 22, display: 'flex',
          alignItems: 'center', justifyContent: 'space-between' }}>
          <div><div style={{ color: '#fff', fontFamily: s.head, fontWeight: 700, fontSize: 20 }}>Meetings & events</div>
            <div style={{ color: '#fff', opacity: 0.8, fontSize: 12, marginTop: 4 }}>RFP in 24h · catering included</div></div>
          <Btn solid={false} style={{ background: '#fff', border: 'none' }}>Request proposal</Btn>
        </div></Sec>
        <VGap h={26} />
        <Sec><H size={18} style={{ marginBottom: 12 }}>Rooms & rates</H>
          <Grid cols={3} gap={16}>
            {['Standard', 'Executive', 'Suite'].map((r) => (
              <Col key={r} gap={8}><Ph h={120} /><div style={{ fontWeight: 700, fontSize: 13 }}>{r}</div>
                <Lines n={1} h={6} w="60%" /></Col>
            ))}
          </Grid></Sec>
        <VGap h={24} />
        <Sec><Row gap={20} align="stretch" style={{ background: s.fill, borderRadius: s.radius, padding: 16 }}>
          <Ph h={120} w="40%" bind="location.map" />
          <Col gap={8} style={{ flex: 1, justifyContent: 'center' }}>
            <H size={18}>5 min from Central Station</H><Lines n={3} bind="location.directions" />
          </Col>
        </Row></Sec>
        <VGap h={26} />
        <DiningTeaser reverse />
        <VGap h={26} />
        <Reviews />
        <VGap h={26} />
        <GalleryStrip cols={4} />
        <VGap h={26} />
        <Newsletter />
        <VGap h={26} />
      </>}

      {styleKey === 'resort' && <>
        <Nav links={['Stay', 'Experiences', 'Spa', 'Offers']} cta="Reserve" />
        <Ph h={420} radius={0} bind="hero.image" style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 18, textAlign: 'center' }}>
            <H size={50} bind="hero.title" style={{ color: '#fff', textShadow: '0 2px 12px rgba(0,0,0,.35)' }} w={560}>Your island escape awaits</H>
            <Row gap={14}><Btn size="lg">Reserve your stay</Btn>
              <Btn size="lg" solid={false} style={{ color: '#fff', borderColor: 'rgba(255,255,255,.7)' }}>Watch film</Btn></Row>
          </div>
        </Ph>
        <Sec style={{ marginTop: -32, position: 'relative', zIndex: 2 }}>
          <BookingBar fields={['Check-in', 'Check-out', 'Guests', 'Rooms']} cta="Find your villa" bind="bookingWidget (plugin)" />
        </Sec>
        <VGap h={28} />
        <Sec><H size={26} bind="experiences.title" style={{ textAlign: 'center', marginBottom: 18 }}>Choose your experience</H>
          <Grid cols={2} gap={s.gap}>
            {['Infinity pool', 'Beach club', 'Spa & wellness', 'Island dining'].map((e, i) => (
              <div key={e} style={{ position: 'relative', borderRadius: s.radius, overflow: 'hidden' }}>
                <Ph h={150} bind={`experiences[${i}].image`} />
                <div style={{ position: 'absolute', left: 16, bottom: 14, color: '#fff', zIndex: 2,
                  fontFamily: s.head, fontWeight: 700, fontSize: 19, textShadow: '0 1px 6px rgba(0,0,0,.4)' }}>{e}</div>
              </div>
            ))}
          </Grid></Sec>
        <VGap h={34} />
        <Sec style={{ background: s.accentSoft, padding: `26px ${s.pad}px`, borderRadius: s.radius }}>
          <H size={22} style={{ marginBottom: 14 }}>Packages & escapes</H>
          <Grid cols={3} gap={16}>
            {['Honeymoon', 'Family week', 'Wellness retreat'].map((p, i) => (
              <Col key={p} gap={8} style={{ background: '#fff', borderRadius: s.radius, padding: 14 }}>
                <Ph h={90} bind={`offers[${i}].image`} /><div style={{ fontWeight: 700, fontSize: 14 }}>{p}</div><Lines n={1} /></Col>
            ))}
          </Grid></Sec>
        <VGap h={34} />
        <DiningTeaser />
        <VGap h={34} />
        <Reviews />
        <VGap h={34} />
        <GalleryStrip cols={4} />
        <VGap h={34} />
        <LocationTeaser />
        <VGap h={34} />
        <Newsletter />
        <VGap h={34} />
      </>}

      <Footer />
    </Page>
  );
}

// ── ROOMS (LISTING) ─────────────────────────────────────────────
function RoomsList({ styleKey }) {
  const s = STYLES[styleKey];
  const RoomRow = ({ name, big, i = 0 }) => (
    <Row gap={20} align="stretch" style={{ paddingBottom: 20, borderBottom: `1px solid ${s.line}` }}>
      <Ph h={big ? 180 : 130} w="42%" bind={`rooms[${i}].image`} />
      <Col gap={10} style={{ flex: 1, justifyContent: 'center' }}>
        <H size={big ? 26 : 20} bind={`rooms[${i}].name`}>{name}</H><Lines n={2} bind={`rooms[${i}].summary`} />
        <Row gap={8} wrap><Chip>32 m²</Chip><Chip>Sea view</Chip><Chip>King bed</Chip></Row>
        <Row justify="space-between" align="flex-end" style={{ marginTop: 4 }}>
          <B b={`rooms[${i}].priceFrom`}><span style={{ fontFamily: s.head, fontSize: 18, color: s.accent }}>from $120</span></B><Btn>View room</Btn>
        </Row>
      </Col>
    </Row>
  );
  return (
    <Page styleKey={styleKey}>
      <Nav cta={styleKey === 'budget' ? 'Book now' : 'Reserve'} utility={styleKey === 'business'} />

      {styleKey === 'budget' ? <>
        <Sec style={{ marginTop: 16 }}><BookingBar fields={['Check-in', 'Check-out', 'Guests']} cta="Update" /></Sec>
        <VGap h={14} />
        <Sec><Row gap={16} align="flex-start">
          {/* filters rail */}
          <Col gap={12} style={{ width: 150, flexShrink: 0 }}>
            <div style={{ fontWeight: 700, fontSize: 12 }}>Filter</div>
            {['Price', 'Bed type', 'Free cancel', 'Breakfast', 'Rating'].map((f) => (
              <Row key={f} gap={8}><Box h={14} w={14} radius={3} /><span style={{ fontSize: 11.5, color: s.muted }}>{f}</span></Row>
            ))}
            <Box h={60} radius={s.radius} style={{ marginTop: 6 }} />
          </Col>
          <Col gap={10} style={{ flex: 1 }}>
            <Row justify="space-between"><span style={{ fontSize: 12, color: s.muted }}>14 rooms · sorted by price</span>
              <Chip>Sort ▾</Chip></Row>
            {[['Single', '59'], ['Double', '74'], ['Twin', '74'], ['Family', '98'], ['Suite', '140']].map(([r, p], i) => (
              <Row key={r} gap={12} align="stretch" style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
                <Ph h={92} w={130} radius={0} bind={`rooms[${i}].image`} />
                <Col gap={4} style={{ flex: 1, justifyContent: 'center', padding: '8px 0' }}>
                  <B b={`rooms[${i}].name`}><span style={{ fontWeight: 700, fontSize: 13 }}>{r} Room</span></B><Stars n={4} />
                  <Row gap={6}><Chip>Free WiFi</Chip><Chip>25 m²</Chip></Row></Col>
                <Col gap={6} style={{ justifyContent: 'center', alignItems: 'flex-end', padding: '8px 12px', minWidth: 90 }}>
                  <B b={`rooms[${i}].priceFrom`}><span style={{ fontWeight: 800, fontSize: 18, color: s.price }}>${p}</span></B>
                  <Btn size="sm">Reserve</Btn></Col>
              </Row>
            ))}

          </Col>
        </Row></Sec>
      </> : styleKey === 'boutique' ? <>
        <VGap h={36} />
        <Sec><div style={{ textAlign: 'center', maxWidth: 460, margin: '0 auto' }}>
          <Kicker>The rooms</Kicker><H size={32} style={{ margin: '10px 0' }}>Twelve ways to stay</H>
          <Lines n={2} h={7} gap={9} last="60%" style={{ alignItems: 'center' }} /></div></Sec>
        <VGap h={40} />
        <Sec><Col gap={36}>
          <RoomRow name="The Garden Room" big i={0} />
          <RoomRow name="Sea Suite" big i={1} />
          <RoomRow name="The Atelier" big i={2} />
        </Col></Sec>
        <VGap h={36} />
      </> : styleKey === 'business' ? <>
        <Sec style={{ marginTop: 22 }}><Row justify="space-between" align="flex-end" style={{ marginBottom: 14 }}>
          <div><Kicker>Accommodation</Kicker><H size={26} style={{ marginTop: 6 }}>Rooms & rates</H></div>
          <Row gap={8}><Chip>Best flexible</Chip><Chip>Corporate rate ▾</Chip></Row>
        </Row>
        <Grid cols={2} gap={s.gap}>
          {['Standard King', 'Executive', 'Junior Suite', 'Boardroom Suite'].map((r, i) => (
            <Col key={r} gap={10} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 14 }}>
              <Ph h={120} bind={`rooms[${i}].image`} /><H size={15} bind={`rooms[${i}].name`}>{r}</H>
              <Row gap={6} wrap><Chip>28 m²</Chip><Chip>Work desk</Chip><Chip>2 guests</Chip></Row>
              <Row justify="space-between" align="center" style={{ borderTop: `1px solid ${s.line}`, paddingTop: 10 }}>
                <B b={`rooms[${i}].priceFrom`}><span style={{ fontWeight: 700, fontSize: 15 }}>$185 <span style={{ fontSize: 11, color: s.muted, fontWeight: 400 }}>/ night</span></span></B>
                <Btn size="sm">Select</Btn></Row>
            </Col>
          ))}
        </Grid></Sec>
        <VGap h={26} />
      </> : <>
        <VGap h={28} />
        <Sec><H size={28} style={{ textAlign: 'center', marginBottom: 6 }}>Rooms & villas</H>
          <div style={{ textAlign: 'center', fontSize: 13, color: s.muted, marginBottom: 22 }}>Wake up to the ocean</div>
          <Grid cols={2} gap={s.gap}>
            {['Garden Bungalow', 'Ocean Villa', 'Overwater Suite', 'Beach House'].map((r, i) => (
              <Col key={r} gap={10} style={{ background: '#fff', borderRadius: s.radius, overflow: 'hidden',
                boxShadow: '0 6px 22px rgba(0,0,0,.06)' }}>
                <Ph h={150} radius={0} bind={`rooms[${i}].image`} />
                <div style={{ padding: '0 16px 16px' }}>
                  <H size={20} bind={`rooms[${i}].name`}>{r}</H><Lines n={1} bind={`rooms[${i}].summary`} style={{ margin: '8px 0' }} />
                  <Row justify="space-between" align="center"><B b={`rooms[${i}].priceFrom`}><span style={{ fontWeight: 700, color: s.accent }}>from $340</span></B>
                    <Btn size="sm">Explore</Btn></Row></div>
              </Col>
            ))}
          </Grid></Sec>
        <VGap h={28} />
      </>}

      <Footer />
    </Page>
  );
}

// ── ROOM DETAIL ─────────────────────────────────────────────────
function RoomDetail({ styleKey }) {
  const s = STYLES[styleKey];
  const amen = ['King bed', 'Sea view', 'Free WiFi', 'Air-con', 'Minibar', 'Work desk', 'Bath', 'Balcony'];
  return (
    <Page styleKey={styleKey}>
      <Nav cta={styleKey === 'budget' ? 'Book now' : 'Reserve'} utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <Ph h={360} radius={0} bind="room.image" />
        <VGap h={34} />
        <Sec><Row gap={40} align="flex-start">
          <Col gap={18} style={{ flex: 1 }}>
            <div><Kicker bind="room.label">Room 04</Kicker><H size={36} bind="room.name" style={{ marginTop: 8 }}>The Sea Suite</H></div>
            <Lines n={4} bind="room.description" />
            <div style={{ borderTop: `1px solid ${s.line}`, paddingTop: 16 }}>
              <H size={18} style={{ marginBottom: 12 }}>In this room</H>
              <B b="room.amenities[]"><Grid cols={2} gap={10}>{amen.map((a) => <span key={a} style={{ fontSize: 13, color: s.muted }}>— {a}</span>)}</Grid></B>
            </div>
          </Col>
          <Col gap={14} style={{ width: 240, flexShrink: 0, borderLeft: `1px solid ${s.line}`, paddingLeft: 28 }}>
            <B b="room.priceFrom"><span style={{ fontFamily: s.head, fontSize: 26 }}>$240<span style={{ fontSize: 13, color: s.muted }}> / night</span></span></B>
            <Lines n={2} /><Btn size="lg" style={{ width: '100%' }}>Enquire to book</Btn>
          </Col>
        </Row></Sec>
        <VGap h={32} />
        <Sec><Grid cols={3} gap={12}>{[0, 1, 2].map((i) => <Ph key={i} h={120} />)}</Grid></Sec>
        <VGap h={30} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 14 }}>
          <span style={{ fontSize: 11, color: s.muted }}>Rooms › Double Room</span>
          <Row gap={6} align="center" style={{ margin: '6px 0' }}><H size={22} bind="room.name">Double Room</H><Chip accent>★ 8.9</Chip></Row>
          <B b="room.gallery[]" style={{ display: 'block' }}><Grid cols={3} gap={6} style={{ marginBottom: 14 }}>
            <Ph h={150} radius={0} style={{ gridRow: 'span 2', height: '100%' }} />
            <Ph h={72} radius={0} /><Ph h={72} radius={0} /><Ph h={72} radius={0} /><Ph h={72} radius={0} />
          </Grid></B>
          <Row gap={16} align="flex-start">
            <Col gap={12} style={{ flex: 1 }}>
              <B b="room.amenities[]"><Row gap={6} wrap>{amen.map((a) => <Chip key={a}>✓ {a}</Chip>)}</Row></B>
              <Lines n={3} bind="room.description" />
              <div style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 10 }}>
                <div style={{ fontWeight: 700, fontSize: 12, marginBottom: 8 }}>Choose your rate</div>
                {['Standard · pay now', 'Flexible · free cancel'].map((r, i) => (
                  <Row key={r} justify="space-between" style={{ padding: '8px 0', borderTop: i ? `1px solid ${s.line}` : 'none' }}>
                    <span style={{ fontSize: 12 }}>{r}</span><span style={{ fontWeight: 800, color: s.price }}>${74 + i * 12}</span></Row>
                ))}
              </div>
            </Col>
            <Col gap={10} style={{ width: 170, flexShrink: 0, border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 12 }}>
              <span style={{ fontSize: 11, color: s.muted }}>from</span>
              <span style={{ fontWeight: 800, fontSize: 24, color: s.price }}>$74</span>
              <Lines n={2} /><Btn style={{ width: '100%' }}>Reserve now</Btn>
              <span style={{ fontSize: 10, color: s.muted, textAlign: 'center' }}>No prepayment needed</span>
            </Col>
          </Row>
        </Sec>
        <VGap h={16} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 20 }}><span style={{ fontSize: 11, color: s.muted }}>Rooms / Executive Room</span>
          <H size={26} bind="room.name" style={{ margin: '8px 0 14px' }}>Executive Room</H>
          <Row gap={20} align="flex-start">
            <Col gap={12} style={{ flex: 1.3 }}>
              <Ph h={240} bind="room.image" /><B b="room.gallery[]" style={{ display: 'block' }}><Grid cols={4} gap={8}>{[0, 1, 2, 3].map((i) => <Ph key={i} h={56} />)}</Grid></B>
              <div style={{ borderTop: `2px solid ${s.accent}`, paddingTop: 12, marginTop: 4 }}>
                <H size={16} style={{ marginBottom: 10 }}>Room features</H>
                <B b="room.amenities[]"><Grid cols={2} gap={9}>{amen.map((a) => <Row key={a} gap={7}><Box h={6} w={6} radius={99} fill={s.accent} /><span style={{ fontSize: 12, color: s.muted }}>{a}</span></Row>)}</Grid></B>
              </div>
            </Col>
            <Col gap={12} style={{ width: 220, flexShrink: 0, background: s.fill, borderRadius: s.radius, padding: 16 }}>
              <B b="room.priceFrom"><span style={{ fontWeight: 700, fontSize: 22 }}>$185<span style={{ fontSize: 12, color: s.muted, fontWeight: 400 }}> / night</span></span></B>
              <div style={{ fontSize: 11, color: s.muted }}>Corporate rate available</div>
              <Box h={32} br radius={s.radius} /><Box h={32} br radius={s.radius} />
              <Btn style={{ width: '100%' }}>Book this room</Btn>
              <Btn solid={false} style={{ width: '100%' }}>Add to RFP</Btn>
            </Col>
          </Row></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <Ph h={380} radius={0} bind="room.image" style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', left: s.pad, bottom: 24, zIndex: 2 }}>
            <H size={40} bind="room.name" style={{ color: '#fff', textShadow: '0 2px 10px rgba(0,0,0,.4)' }}>Overwater Suite</H></div>
        </Ph>
        <VGap h={28} />
        <Sec><Row gap={26} align="flex-start">
          <Col gap={16} style={{ flex: 1 }}>
            <Lines n={3} bind="room.description" />
            <H size={20}>What you'll love</H>
            <B b="room.amenities[]"><Grid cols={2} gap={12}>{amen.slice(0, 6).map((a) => (
              <Row key={a} gap={9} style={{ background: s.accentSoft, borderRadius: s.radius, padding: '10px 12px' }}>
                <Box h={18} w={18} radius={99} /><span style={{ fontSize: 12, fontWeight: 600 }}>{a}</span></Row>))}</Grid></B>
          </Col>
          <Col gap={14} style={{ width: 230, flexShrink: 0, background: '#fff', borderRadius: s.radius, padding: 18,
            boxShadow: '0 8px 26px rgba(0,0,0,.08)' }}>
            <B b="room.priceFrom"><span style={{ fontFamily: s.head, fontWeight: 700, fontSize: 24, color: s.accent }}>$420<span style={{ fontSize: 13, color: s.muted, fontWeight: 500 }}>/night</span></span></B>
            <BookingBar vertical fields={['Dates', 'Guests']} cta="Check dates" style={{ boxShadow: 'none', padding: 0, border: 'none' }} />
            <Btn size="lg" style={{ width: '100%' }}>Reserve villa</Btn>
          </Col>
        </Row></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

Object.assign(window, { Landing, RoomsList, RoomDetail });
