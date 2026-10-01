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

// ------------------------------------------------------------------ page setup

#set document(title: profile.name + " CV", author: profile.name)
#set page(
  paper: "us-letter",
  margin: (x: 0.55in, top: 0.6in, bottom: 0.7in),
  footer: context align(center, text(size: 10pt, counter(page).display())),
)
// Palatino on macOS; TeX Gyre Pagella (metric-compatible clone) in CI.
#set text(font: ("Palatino", "Palatino Linotype", "TeX Gyre Pagella"), size: 10pt, lang: "en")
#set par(leading: 0.42em, spacing: 0.42em)
#show link: set text(fill: rgb("#1155cc"))
#show link: underline

// ------------------------------------------------------------------ helpers

#let md(s) = if s == none { [] } else { eval(str(s), mode: "markup") }
#let get(d, k) = d.at(k, default: none)

#let section(title) = {
  v(1.1em, weak: true)
  align(center, text(weight: "bold", size: 11pt, upper(title)))
  v(0.55em)
}

// A line with content on the left and a bold-italic date flush right.
#let dated(left, right, right-style: "bold-italic") = {
  let r = if right == none { [] } else if right-style == "plain" { [#right] } else {
    text(style: "italic", weight: "bold", right)
  }
  grid(columns: (1fr, auto), column-gutter: 1em, left, r)
}

#let entry-gap = v(0.95em, weak: true)

#let position(p) = {
  dated([*#p.role.* #p.org], get(p, "dates"))
  if get(p, "detail") != none { md(p.detail) }
}

#let month-year(s) = {
  let (y, m) = str(s).split("-").map(int)
  datetime(year: y, month: m, day: 1).display("[month repr:long] [year]")
}

// Bold the CV owner's name (with or without equal-contribution *).
#let author(a) = {
  if a.trim("*") == profile.author_name { strong(a) } else { a }
}

#let citation(p) = {
  let when = if get(p, "status") != none { emph(p.status) } else {
    p.at("date_label", default: str(p.year))
  }
  let parts = ()
  parts.push(p.authors.map(author).join(", ") + [ (#when). ])
  parts.push([#p.title. ])
  parts.push(emph(p.venue))
  if get(p, "details") != none { parts.push([. #p.details]) }
  parts.push([.])
  if get(p, "doi") != none {
    let url = "https://doi.org/" + p.doi
    parts.push([ #link(url, url)])
  }
  if get(p, "note") != none { parts.push([ *[#p.note]*]) }
  par(spacing: 0.9em, parts.join())
}

// Newest first; forthcoming ("In Press") items before everything.
#let sort-pubs(xs) = xs.sorted(key: p => -p.at("year", default: 9999))

#let pub-list(kind) = {
  for p in sort-pubs(pubs.filter(p => p.type == kind)) { citation(p) }
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

#section("Teaching")
#for t in teaching {
  dated(strong(t.title), t.dates)
  md(t.detail)
}

#section("Peer-Reviewed Journal Articles & Conference Proceedings")
#align(center, text(size: 9pt, weight: "bold")[
  \[#link(profile.scholar.url) : #profile.scholar.citations citations, h-index #profile.scholar.h_index\] \
  \*denotes equal contribution
])
#v(0.4em)
#pub-list("article")

#section("Preprints")
#pub-list("preprint")

#section("Blog Posts")
#pub-list("blog")

#section("Conference and Workshop Talks")
#talk-list(talks.conference)

#section("Seminar and Colloquium Talks")
#talk-list(talks.seminar)

#section("Academic Duties & Community Involvement")
#for s in service {
  par(hanging-indent: 0.4in, spacing: 0.9em, [*#s.label:* #md(s.text)])
}
