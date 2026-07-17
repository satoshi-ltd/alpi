/* pages-blog.jsx — Blog (listing) + Post (single article). Branch on styleKey. */

// ── BLOG (LISTING) ──────────────────────────────────────────────
function Blog({ styleKey }) {
  const s = STYLES[styleKey];
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'Journal', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={40} />
        <Sec><div style={{ textAlign: 'center' }}><Kicker>Journal</Kicker><H size={34} bind="page.title" style={{ marginTop: 10 }}>Notes from the house</H></div></Sec>
        <VGap h={36} />
        {/* featured */}
        <Sec><Row gap={32} align="center">
          <Ph h={280} w="56%" bind="posts[0].cover" />
          <Col gap={12} style={{ flex: 1 }}><Kicker bind="posts[0].category">Featured · Slow travel</Kicker>
            <H size={28} bind="posts[0].title">A morning ritual by the water</H><Lines n={3} bind="posts[0].excerpt" />
            <span style={{ fontSize: 12, color: s.muted }}>5 min read · June</span></Col>
        </Row></Sec>
        <VGap h={40} />
        <Sec><div style={{ borderTop: `1px solid ${s.line}` }} />
          {['On choosing linen', 'The garden in spring'].map((t, i) => (
            <Row key={t} justify="space-between" align="center" style={{ padding: '20px 0', borderBottom: `1px solid ${s.line}` }}>
              <Col gap={6} style={{ flex: 1 }}><Kicker>Essay</Kicker><H size={22} bind={`posts[${i + 1}].title`}>{t}</H><span style={{ fontSize: 12, color: s.muted }}>4 min read</span></Col>
              <Ph h={90} w={140} bind={`posts[${i + 1}].cover`} /></Row>))}
          </Sec>
        <VGap h={32} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 18 }}><H size={22} bind="page.title" style={{ marginBottom: 4 }}>News & travel tips</H>
          <div style={{ fontSize: 12, color: s.muted, marginBottom: 12 }}>Guides to make your stay cheaper & easier</div>
          <Row gap={8} wrap style={{ marginBottom: 14 }}>{['All', 'City tips', 'Deals', 'How-to'].map((t, i) => <Chip key={t} accent={i === 0}>{t}</Chip>)}</Row>
          <Col gap={10}>{['10 free things to do nearby', 'Best time to book for low prices', 'Getting from the airport for under $5', 'Where locals eat near the hotel'].map((t, i) => (
            <Row key={t} gap={12} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
              <Ph h={72} w={100} radius={0} bind={`posts[${i}].cover`} />
              <Col gap={3} style={{ flex: 1, justifyContent: 'center', padding: '8px 0' }}>
                <B b={`posts[${i}].title`}><span style={{ fontWeight: 700, fontSize: 13 }}>{t}</span></B>
                <span style={{ fontSize: 11, color: s.muted }}>3 min read · Tips</span></Col></Row>))}</Col>
          </Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Kicker>Insights</Kicker><H size={26} style={{ margin: '6px 0 4px' }}>The business traveler's guide</H>
          <div style={{ fontSize: 12.5, color: s.muted, marginBottom: 16 }}>City guides, productivity & travel policy</div>
          <Grid cols={3} gap={s.gap}>
            {['Top 5 meeting spots in the city', 'A 24-hour layover, well spent', 'Expense-friendly dining nearby', 'Working from the lounge', 'Fastest routes to the airport', 'Quiet rooms for calls'].map((t, i) => (
              <Col key={t} gap={9} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
                <Ph h={96} radius={0} bind={`posts[${i}].cover`} />
                <div style={{ padding: '0 12px 12px' }}>
                  <Chip>City guide</Chip>
                  <B b={`posts[${i}].title`}><div style={{ fontWeight: 700, fontSize: 13, margin: '8px 0 6px' }}>{t}</div></B>
                  <span style={{ fontSize: 11, color: s.muted }}>By Editorial · 4 min</span></div></Col>
            ))}
          </Grid></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <VGap h={26} />
        <Sec><H size={28} bind="page.title" style={{ textAlign: 'center', marginBottom: 6 }}>Island stories</H>
          <div style={{ textAlign: 'center', fontSize: 13, color: s.muted, marginBottom: 22 }}>Life, nature and adventure on the atoll</div>
          <Grid cols={2} gap={s.gap}>
            {[['Swimming with manta rays', 'Adventure'], ['A day in the life of our reef', 'Nature'], ['Sunset rituals worth waking for', 'Experiences'], ['Meet the island chefs', 'People']].map(([t, c], i) => (
              <Col key={t} gap={0} style={{ background: '#fff', borderRadius: s.radius, overflow: 'hidden', boxShadow: '0 6px 22px rgba(0,0,0,.06)' }}>
                <div style={{ position: 'relative' }}><Ph h={150} radius={0} bind={`posts[${i}].cover`} />
                  <span style={{ position: 'absolute', top: 12, left: 12, zIndex: 3, background: '#fff', color: s.accent, fontSize: 11, fontWeight: 700, padding: '4px 10px', borderRadius: 99 }}>{c}</span></div>
                <div style={{ padding: 16 }}><H size={20} bind={`posts[${i}].title`}>{t}</H><span style={{ fontSize: 12, color: s.muted }}>6 min read</span></div></Col>
            ))}
          </Grid></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

// ── POST (SINGLE ARTICLE) ───────────────────────────────────────
function Post({ styleKey }) {
  const s = STYLES[styleKey];
  const related = (t) => (
    <Col gap={8}><Ph h={90} /><div style={{ fontWeight: 600, fontSize: 12.5, fontFamily: s.head }}>{t}</div></Col>
  );
  return (
    <Page styleKey={styleKey}>
      <Nav links={['Rooms', 'Amenities', 'Journal', 'Contact']} cta={styleKey === 'budget' ? 'Book now' : 'Reserve'}
        utility={styleKey === 'business'} />

      {styleKey === 'boutique' && <>
        <VGap h={42} />
        <Sec><div style={{ maxWidth: 600, margin: '0 auto', textAlign: 'center' }}>
          <Kicker>Essay · Slow travel</Kicker>
          <H size={40} bind="post.title" style={{ margin: '16px 0' }}>A morning ritual by the water</H>
          <span style={{ fontSize: 12, color: s.muted }}>By the house · 5 min read</span></div></Sec>
        <VGap h={32} />
        <Sec><Ph h={320} bind="post.cover" /></Sec>
        <VGap h={34} />
        <Sec><div style={{ maxWidth: 600, margin: '0 auto' }}>
          <Lines n={5} bind="post.body" />
          <div style={{ borderLeft: `2px solid ${s.accent}`, paddingLeft: 20, margin: '28px 0' }}>
            <H size={24} style={{ fontStyle: 'italic' }}>"The sea asks nothing of you before coffee."</H></div>
          <Lines n={4} />
          </div></Sec>
        <VGap h={32} />
      </>}

      {styleKey === 'budget' && <>
        <Sec style={{ marginTop: 16 }}><span style={{ fontSize: 11, color: s.muted }}>Blog › Tips</span>
          <H size={24} bind="post.title" style={{ margin: '8px 0' }}>Getting from the airport for under $5</H>
          <span style={{ fontSize: 11.5, color: s.muted }}>3 min read · Updated June</span>
          <Ph h={170} radius={s.radius} bind="post.cover" style={{ margin: '14px 0' }} />
          <Lines n={4} bind="post.body" />
          <div style={{ background: s.accentSoft, borderRadius: s.radius, padding: 12, margin: '14px 0' }}>
            <div style={{ fontWeight: 700, fontSize: 12.5, marginBottom: 6 }}>Quick steps</div>
            <Lines n={3} h={6} gap={8} last="50%" /></div>
          <Lines n={3} h={7} gap={10} last="45%" />
          <div style={{ marginTop: 18 }}><div style={{ fontWeight: 700, fontSize: 13, marginBottom: 8 }}>Read next</div>
            <Grid cols={3} gap={10}>{['Free things nearby', 'Where locals eat', 'Best booking times'].map((t) => (
              <Col key={t} gap={6} style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, overflow: 'hidden' }}>
                <Ph h={60} radius={0} /><span style={{ fontSize: 11, fontWeight: 600, padding: '0 8px 8px' }}>{t}</span></Col>))}</Grid></div>
          <Note style={{ marginTop: 12 }}>artículo simple + relacionados</Note></Sec>
        <VGap h={18} />
      </>}

      {styleKey === 'business' && <>
        <Sec style={{ marginTop: 22 }}><Row gap={28} align="flex-start">
          <Col gap={14} style={{ flex: 1 }}>
            <Chip>City guide</Chip>
            <H size={28} bind="post.title">Top 5 meeting spots in the city</H>
            <Row gap={10} align="center"><Box h={28} w={28} radius={99} /><Col gap={1}><span style={{ fontSize: 12, fontWeight: 600 }}>Editorial team</span><span style={{ fontSize: 11, color: s.muted }}>4 min read · June</span></Col></Row>
            <Ph h={200} bind="post.cover" style={{ marginTop: 6 }} />
            <Lines n={4} bind="post.body" />
            <H size={16} style={{ marginTop: 8 }}>1 · The lobby lounge</H><Lines n={3} h={6} gap={9} last="60%" />
          </Col>
          <Col gap={14} style={{ width: 200, flexShrink: 0 }}>
            <div style={{ border: `1px solid ${s.line}`, borderRadius: s.radius, padding: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 12 }}>In this article</div>
              <Col gap={7} style={{ marginTop: 8 }}>{['The lobby lounge', 'Café district', 'Co-working spots'].map((t) => <span key={t} style={{ fontSize: 11.5, color: s.muted }}>— {t}</span>)}</Col></div>
            <Row gap={8}>{['Share', 'Save'].map((b) => <Btn key={b} size="sm" solid={false} style={{ flex: 1 }}>{b}</Btn>)}</Row>
            <Note>TOC + meta + autor</Note></Col>
        </Row></Sec>
        <VGap h={24} />
      </>}

      {styleKey === 'resort' && <>
        <Ph h={360} radius={0} bind="post.cover" style={{ position: 'relative' }}>
          <div style={{ position: 'absolute', left: s.pad, right: s.pad, bottom: 26, textAlign: 'center', zIndex: 2 }}>
            <span style={{ display: 'inline-block', background: '#fff', color: s.accent, fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 99, marginBottom: 12 }}>Adventure</span>
            <H size={36} bind="post.title" style={{ color: '#fff', textShadow: '0 2px 12px rgba(0,0,0,.4)' }}>Swimming with manta rays</H></div>
        </Ph>
        <VGap h={28} />
        <Sec><div style={{ maxWidth: 620, margin: '0 auto' }}>
          <Lines n={4} bind="post.body" />
          <Grid cols={2} gap={12} style={{ margin: '20px 0' }}><Ph h={140} radius={s.radius} /><Ph h={140} radius={s.radius} /></Grid>
          <Lines n={3} /></div></Sec>
        <VGap h={26} />
        <Sec style={{ background: s.accentSoft, padding: `22px ${s.pad}px`, borderRadius: s.radius }}>
          <H size={20} style={{ marginBottom: 14 }}>More island stories</H>
          <Grid cols={3} gap={14}>{['The reef at dawn', 'Sunset rituals', 'Meet the chefs'].map((t) => (
            <Col key={t} gap={8} style={{ background: '#fff', borderRadius: s.radius, overflow: 'hidden' }}>
              <Ph h={80} radius={0} /><span style={{ fontSize: 12, fontWeight: 600, fontFamily: s.head, padding: '0 10px 10px' }}>{t}</span></Col>))}</Grid>
          <Note style={{ marginTop: 12 }}>hero inmersivo + galería + stories</Note></Sec>
        <VGap h={26} />
      </>}

      <Footer />
    </Page>
  );
}

Object.assign(window, { Blog, Post });
