// Academic CV template. Reads everything from /data/*.yaml.
// Build with: uv run python -m cvtool.build

#let profile = yaml("/data/profile.yaml")
#let positions = yaml("/data/positions.yaml")
#let education = yaml("/data/education.yaml")
#let awards = yaml("/data/awards.yaml")
#let teaching = yaml("/data/teaching.yaml")
#let pubs = yaml("/data/publications.yaml")
#let talks = yaml("/data/talks.yaml")
#let service = yaml("/data/service.yaml")
#let grants = yaml("/data/grants.yaml")
#let venues = yaml("/data/venues.yaml")

// ------------------------------------------------------------------ page setup

#set document(title: profile.name + " CV", author: profile.name)
#set page(
  paper: "us-letter",
  margin: (x: 0.55in, top: 0.6in, bottom: 0.7in),
  footer: context align(center, text(size: 10pt, counter(page).display())),
)
// Palatino on macOS; TeX Gyre Pagella (metric-compatible clone) in CI.
#set text(font: ("Palatino", "Palatino Linotype", "TeX Gyre Pagella"), size: 10pt, lang: "en")
#set par(leading: 0.6em, spacing: 0.6em)
#set block(spacing: 0.6em)
#show link: set text(fill: rgb("#1155cc"))
#show link: underline

// ------------------------------------------------------------------ helpers

#let md(s) = if s == none { [] } else { eval(str(s), mode: "markup") }
#let get(d, k) = d.at(k, default: none)

// Headings are blocks with equal space above and below.
#let section(title) = block(above: 1.3em, below: 1.3em, width: 100%, sticky: true,
  align(center, text(weight: "bold", size: 11pt, upper(title))))

#let subsection(title) = block(above: 1.1em, below: 1.1em, width: 100%, sticky: true,
  align(center, text(weight: "bold", style: "italic", size: 10.5pt, title)))

// A line with content on the left and a bold-italic date flush right.
#let dated(left, right, right-style: "bold-italic") = {
  if right == none { return block(left) }
  let r = if right-style == "plain" { [#right] } else {
    text(style: "italic", weight: "bold", right)
  }
  grid(columns: (1fr, auto), column-gutter: 1em, left, r)
}

#let entry-gap = v(1.1em, weak: true)

#let position(p) = {
  dated([*#p.role.* #p.org], get(p, "dates"))
  if get(p, "detail") != none { md(p.detail) }
}

#let year-range(g) = {
  let (a, b) = (str(g.start).slice(0, 4), str(g.end).slice(0, 4))
  if a == b { a } else { a + " – " + b }
}

#let commas(n) = {
  let s = str(n)
  let out = ""
  for (i, c) in s.clusters().enumerate() {
    if i > 0 and calc.rem(s.len() - i, 3) == 0 { out += "," }
    out += c
  }
  out
}

#let grant(g) = {
  dated(strong(g.title), year-range(g))
  let role = if get(g, "detail") != none { md(g.detail) } else {
    let others = g.at("with", default: ())
    let extra = if g.role == "MPI" and get(g, "contact") != none {
      " (Contact PI: " + g.contact + if others.len() > 0 { "; with " + others.join(", ") } else { "" } + ")"
    } else if others.len() > 0 {
      " (with " + others.join(", ") + ")"
    } else { "" }
    [Role: #g.role#extra.]
  }
  let amount = if profile.at("grants_show_amounts", default: false) and get(g, "amount") != none {
    [ \$#commas(g.amount)]
  }
  [_#g.agency #g.id._ #role#amount]
}

#let month-year(s) = {
  let (y, m) = str(s).split("-").map(int)
  datetime(year: y, month: m, day: 1).display("[month repr:long] [year]")
}

// Bold the CV owner's name (with or without equal-contribution *).
#let author(a) = {
  if a.trim("*") == profile.author_name { strong(a) } else { a }
}

// Where a citation links to: `url` if set, else arXiv abstract page, else DOI.
#let paper-url(p) = {
  let doi = str(p.at("doi", default: ""))
  let arxiv = if get(p, "arxiv") != none { str(p.arxiv) } else if doi.starts-with("10.48550/arxiv.") {
    doi.slice(15)
  }
  if get(p, "url") != none { p.url }
  else if arxiv != none { "https://arxiv.org/abs/" + arxiv }
  else if doi != "" { "https://doi.org/" + doi }
}

// " [paper]" link printed after journal, conference and preprint citations.
#let paper-link(p) = {
  let url = paper-url(p)
  if url != none {
    let label = p.at("link_label", default: "paper")
    [ #link(url)[\[#label\]]]
  }
}

#let citation(p) = {
  let when = if get(p, "status") != none { emph(p.status) } else {
    p.at("date_label", default: str(p.year))
  }
  let parts = ()
  parts.push(p.authors.map(author).join(", ") + [ (#when). ])
  parts.push([#p.title. ])
  if p.type == "conference" {
    // Standard form: *Full Name[, Track]* (KEY). [paper]
    let v = venues.at(p.venue, default: none)
    let name = if v != none { v.name } else { p.venue }
    if get(p, "track") != none { name += ", " + p.track }
    parts.push(emph(name))
    if v != none { parts.push([ (#p.venue)]) }
    parts.push([.])
  } else {
    parts.push(emph(p.venue))
    if get(p, "details") != none { parts.push([. #p.details]) }
    parts.push([.])
  }
  if p.type in ("journal", "conference", "preprint") { parts.push(paper-link(p)) }
  // Blog posts print the full address, as on the original CV.
  if p.type == "blog" and paper-url(p) != none {
    parts.push([ #link(paper-url(p))])
  }
  if get(p, "note") != none { parts.push([ *[#p.note]*]) }
  par(spacing: 1.1em, parts.join())
}

// Newest first; forthcoming ("In Press") items before everything.
#let sort-pubs(xs) = xs.sorted(key: p => -p.at("year", default: 9999))

#let pub-list(kind) = {
  for p in sort-pubs(pubs.filter(p => p.type == kind)) { citation(p) }
}

// Explanatory note under a (sub)heading: indented, gray italics, pulled up close.
#let pub-note(body) = {
  v(-0.5em)
  block(sticky: true, inset: (x: 0.35in), below: 1.1em,
    text(size: 9.5pt, style: "italic", fill: luma(30%), par(justify: true, md(body))))
}

// A subsection of preprints in one `category`, with an optional note; omitted if empty.
#let preprint-section(title, category, note: none) = {
  let xs = pubs.filter(p => p.type == "preprint" and p.at("category", default: "in-prep") == category)
  if xs.len() > 0 {
    subsection(title)
    if note != none { pub-note(note) }
    for p in sort-pubs(xs) { citation(p) }
  }
}

#let talk-list(xs) = {
  // Stable sort, newest first: same-month talks keep their file order.
  let key(t) = { let (y, m) = str(t.date).split("-").map(int); -(y * 12 + m) }
  for t in xs.sorted(key: key) {
    par(hanging-indent: 0pt, [*_#month-year(t.date)._* #md(t.text)])
  }
}

// ------------------------------------------------------------------ header

#align(center)[
  #text(weight: "bold", size: 12pt, upper(profile.name)) \
  #text(style: "italic")[
    #profile.tagline #h(0.6em) | #h(0.6em)
    #profile.lab.name: #link(profile.lab.url)
  ]
]
#v(0.2em)
#line(length: 100%, stroke: 0.5pt + gray)
#v(-0.6em)

// ------------------------------------------------------------------ body

#section("Employment")
#for (i, e) in positions.employment.enumerate() {
  if i > 0 { entry-gap }
  if "group" in e { for p in e.group { position(p) } } else { position(e) }
}

#section("Education")
#for (i, e) in education.enumerate() {
  if i > 0 { entry-gap }
  dated([*#e.school.* #e.location], e.dates)
  grid(columns: (1fr, auto), column-gutter: 1em, md(e.detail), md(get(e, "note")))
}

#section("Other Professional Appointments")
#for (i, p) in positions.other_appointments.enumerate() {
  if i > 0 { entry-gap }
  position(p)
}

#section("Awards and Fellowships")
#for a in awards { dated(a.title, a.dates, right-style: "plain") }

#section("Grants")
#for (i, g) in grants.sorted(key: g => str(g.start)).rev().enumerate() {
  if i > 0 { entry-gap }
  grant(g)
}

#section("Teaching")
#for t in teaching {
  dated(strong(t.title), t.dates)
  md(t.detail)
}

#section("Peer-Reviewed Publications")
// Pull the Scholar note up under the heading (negative = closer).
#v(-0.75em)
#block(sticky: true, width: 100%, align(center, text(size: 9pt, weight: "bold")[
  \[#link(profile.scholar.url) : #profile.scholar.citations citations, h-index #profile.scholar.h_index\] \
  \*denotes equal contribution
]))
#subsection("Journal Articles")
#pub-list("journal")
#subsection("Conference Proceedings")
#if profile.at("conference_note", default: none) != none { pub-note(profile.conference_note) }
#pub-list("conference")

#if pubs.any(p => p.type == "preprint") {
  section("Other Manuscripts")
  preprint-section("Manuscripts Under Review", "under-review",
    note: profile.at("under_review_note", default: none))
  preprint-section("Technical Reports", "report",
    note: profile.at("report_note", default: none))
  preprint-section("In Preparation", "in-prep",
    note: profile.at("in_prep_note", default: none))
}

#if pubs.any(p => p.type == "blog") {
  section("Blog Posts")
  pub-list("blog")
}

#section("Conference and Workshop Talks")
#talk-list(talks.conference)

#section("Seminar and Colloquium Talks")
#talk-list(talks.seminar)

#section("Academic Duties & Community Involvement")
#for s in service {
  par(hanging-indent: 0.4in, spacing: 1.1em, [*#s.label:* #md(s.text)])
}
