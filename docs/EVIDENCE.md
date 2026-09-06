# Evidence and claim boundaries

Sources checked during project planning, September 5, 2026. This is a source ledger, not customer validation.

| Source | Supported finding | Boundary |
| --- | --- | --- |
| [Netflix AD style guide](https://partnerhelp.netflixstudios.com/hc/en-us/articles/215510667-Audio-Description-Style-Guide-v2-5) | Deliberately concealed characters should not be named; early naming has legitimate clarity/timing exceptions. | Guidance, not a frequency estimate or proof of automated detection. |
| [Naraine, Fels, and Whitfield, PLOS ONE 2018](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0208165) | 24 blind participants rated eight dark-comedy episodes; description style, language, pace, and fit influenced enjoyment, with differing preferences. | Small study of one show; no Reveal or spoiler-detection evaluation. |
| [Kala et al., ADQA, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.1199/) | Comparison of two AD tracks across 17 movies found about 25–30% of descriptions remained unmatched at a permissive temporal threshold; proposes narrative/visual QA evaluation. | Differences do not imply errors. Benchmark scores are not blind-viewer comprehension rates. This is substantial adjacent prior art. |
| [Starr and Braun, omissions study](https://link.springer.com/article/10.1007/s10209-023-01045-3) | Qualitative analysis of MeMAD film extracts distinguishes omissions recoverable from other cues from those not recoverable. | Does not supply a population-wide rate of missing clues or spoilers. |
| [3Play Pulse announcement](https://www.3playmedia.com/news/press-release-3play-media-launches-pulse-the-first-all-in-one-auditing-and-remediation-solution-for-video-accessibility/) | Commercial AD comprehensiveness auditing already exists. | Vendor claims; public material does not settle whether internal spoiler-review features exist. |

## Defensible positioning

Reveal helps audio-description editors investigate possible premature disclosures using timestamped evidence and suggestions for human review.

No equivalent publicly documented workflow was identified in the reviewed research; this is not proof of novelty or nonexistence of competitors.

## Not established

- Frequency of premature identity disclosure in delivered AD.
- Customer demand, willingness to pay, market size, or time savings.
- Reveal accuracy, impact on suspense/enjoyment, or reviewer acceptance.
- Reliability across genres, languages, disabilities, or full-length films.

Use pilot results only after running the evaluation in PLAN.md. Preserve raw denominators and label seeded examples, model judgments, and human feedback separately.
