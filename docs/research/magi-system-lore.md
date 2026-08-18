# The MAGI System in *Neon Genesis Evangelion*

Research note for `magi-sim`, prepared 2026-08-17. This separates what the original anime actually establishes from useful but non-canonical product interpretation.

## Short version

The original MAGI is not portrayed as three chatbots holding an explicit debate. It is a council of three independent seventh-generation organic computers, each carrying a deliberately different imprint of its creator Dr. Naoko Akagi: **MELCHIOR-1 / scientist**, **BALTHASAR-2 / mother**, and **CASPER-3 / woman**. They evaluate proposals, return votes (including conditional approval), probabilities, and operational decisions. Tokyo-3's municipal government is effectively run by their majority rule, while exceptional commands such as headquarters self-destruction have additional safeguards and are not safely modeled as “ordinary 2–1 wins.”[^tv6][^tv11][^tv13][^eoe]

For this project, three LLM agents, visible arguments, rebuttals, confidence scores, and a convergence controller are a good *Evangelion-inspired* adaptation. They should be described as product mechanics rather than canonical MAGI behavior.

## Canonical facts: original TV series and *The End of Evangelion*

### Identity, construction, and purpose

- The on-screen identifiers are **MELCHIOR-1**, **BALTHASAR-2**, and **CASPER-3**. Together they form the MAGI system.[^tv13]
- Naoko Akagi developed the system while working for Gehirn. Episode 13 describes MAGI as the first application of a **personality-transplant OS** to a seventh-generation organic computer. Ritsuko calls the computers her mother's “brains”; this is personality-pattern language, not proof that each core contains a complete, conscious copy or literal biological brain.[^tv13]
- The three imprints are explicitly mapped as follows:

  | Core | Naoko imprint established in dialogue |
  | --- | --- |
  | MELCHIOR-1 | Naoko as a scientist |
  | BALTHASAR-2 | Naoko as a mother |
  | CASPER-3 | Naoko as a woman |

- Ritsuko says Naoko intentionally left the human dilemma inside MAGI: the three versions of herself oppose one another, and their programs differ slightly. This supports conflicting evaluators. It does **not** supply a detailed policy rubric for any of them.[^tv13]
- MAGI controls or supports NERV Headquarters and, in practice, Tokyo-3's city administration. Episode 11 calls the city council a shell and says the three computers govern by majority decision.[^tv11] *The End of Evangelion* makes the operational stakes explicit: taking MAGI is equivalent to taking Headquarters.[^eoe]
- Their names refer to the traditional names of the Biblical Magi. The Gospel of Matthew itself does not name or number the visitors; Melchior, Balthasar, and Caspar/Gaspar come from later Christian tradition. This distinction matters only if the project explains the name's origin.[^matthew][^filmbook]

### What the three personalities do—and do not imply

The labels **scientist**, **mother**, and **woman** are canon. The following richer descriptions in `initial-planning.md` are not stated by the anime:

- MELCHIOR as purely logical, mathematically utilitarian, emotionally indifferent, or willing to ignore ethics;
- BALTHASAR as a general-purpose ethics/safety/civilian-preservation agent;
- CASPER as “realpolitik,” street-smart pragmatism, self-interest, skepticism, or a contrarian red team.

Those are reasonable prompts for a modern system, but they are interpretive character design. In particular, “mother” is not synonymous with universal ethics, and Naoko's gendered “woman” category is tied in the story to her intimate relationship with Gendo, not to a general doctrine of pragmatism.[^tv13][^eoe]

Casper's behavior is deliberately emotionally charged but not mechanically explained. It is the last core resisting Ireul in Episode 13. In *The End of Evangelion*, when Ritsuko tries to destroy Headquarters, MELCHIOR and BALTHASAR approve while CASPER denies. Ritsuko interprets this as her mother choosing her man over her daughter. The **denial is an on-screen fact**; its inner motive is Ritsuko's interpretation, not an objective explanation from the system.[^eoe]

### Voting and decision behavior shown on screen

1. **Ordinary decisions use majority rule.** Episode 11 says this directly in the context of Tokyo-3 government.[^tv11]
2. **A core can return a qualified answer.** For Operation Yashima in Episode 6, MAGI returns two affirmative votes and one conditional affirmative. The operation's projected success rate is only 8.7%, and Gendo—the human commander—authorizes it. This is strong precedent for `CONDITIONAL` and for presenting analysis to a human instead of treating every result as automatic execution.[^tv6]
3. **Self-destruction is a special case.** In Episode 13, Ireul-controlled MELCHIOR proposes self-destruction and the other cores initially reject it. After BALTHASAR is compromised, a countdown begins while Ireul attacks CASPER. The announcement references Special Command 582 and special multi-core approval/cancellation rules. Subtitle/script translations are inconsistent about the exact threshold, so it is safer not to encode an elaborate rule from one English wording alone.[^tv13][^ep13translation]
4. **A 2–1 result can block self-destruction.** *The End of Evangelion* visibly reports MELCHIOR `APPROVED`, BALTHASAR `APPROVED`, and CASPER `DENIED`; Ritsuko's command does not run.[^eoe] Whether this is a standing unanimity requirement, a consequence of Ritsuko's altered program, or another special safeguard is not fully explained.

Therefore the plan's universal state machine needs correction:

| Claim in `initial-planning.md` | Lore check |
| --- | --- |
| “3–0 approval = automatic execution” | **Too broad.** Unanimity is a result; execution authority depends on the operation. |
| “2–1 = directive executed” | **True for ordinary majority decisions, not universal.** Operation Yashima is still authorized by Gendo; the EoE self-destruct fails at 2–1. |
| “3–0 red = deadlock” | **Incorrect terminology.** Three rejections are unanimous refusal, not a deadlock. |
| “Deadlock requires manual Commander override” | **Unsupported.** No general override rule is established. |
| `AGREE / DISAGREE / CONDITIONAL` | **Good adaptation.** Affirmative and conditional affirmative occur in Episode 6; approve/deny appears in EoE. |
| Confidence score | **Project invention.** MAGI produces probabilities, but the show does not attach calibrated confidence to each core's vote. |

### The Ireul intrusion (Episode 13)

Episode 13, “Angel Invasion / Lilliputian Hitcher,” is the main technical MAGI episode:[^tv13overview]

- Ireul is a colony of microscopic Angel entities that evolves into circuitry and enters NERV's computer system from inside the facility.
- Attempts to shut down I/O or sever control fail. Ireul contacts and rewrites MELCHIOR; the captured core then attacks BALTHASAR.
- Ritsuko changes the logic/synchronization timing, slowing the attack enough to buy roughly two hours.
- Ritsuko and Maya physically open CASPER. Its interior is an organic-industrial maze of cabling, pipes, biological-looking material, access passages, handwritten notes, and back doors left by Naoko.
- Ritsuko directly connects CASPER to the intruder, deliberately lowers the barrier, and sends a program that accelerates Ireul's evolution toward its terminal state: self-extinction. It wins by about one second, after BALTHASAR has fallen and while CASPER is being invaded. The MAGI then returns to normal.

This is better inspiration for an optional **infiltration/counter-hack mode** than “prompt injection” specifically. Prompt injection is a modern analogy; canon depicts adaptive code/network compromise plus a physical wetware intervention. The most Evangelion-like detail is not merely hostile input—it is allowing a dangerous direct connection to counter-evolve the attacker.

### SEELE's attack and Ritsuko's override (*The End of Evangelion*)

- SEELE launches a coordinated external intrusion using at least five other MAGI-type systems. Dialogue identifies Matsushiro and attacks from Germany, China, and the United States; the defenders describe being outnumbered five to one.[^eoe]
- The attack penetrates successive firewalls and external/auxiliary blocks. Ritsuko installs a defense identified in translations as a B-DANAN firewall and by SEELE as “protection 666,” buying 62 hours and forcing SEELE to abandon a clean digital seizure in favor of a physical assault.[^eoe]
- Later, Ritsuko says she altered MAGI's programming and issues a self-destruction request. CASPER denies it while the other two approve; no commander override rescues the command.[^eoe]

The “type-666 firewall” phrase commonly used by fans compresses two nearby pieces of dialogue. Use **protection 666** as the safer screen-lore label unless the project intentionally adopts a particular subtitle localization.

## Visual and interaction language

### Directly supported motifs

- **Three-part geometry:** the three named core readouts are presented together as a council, commonly in a triangular/overlapping arrangement. The physical machines are also grouped as a triad.[^tv13][^eoe]
- **Dense technical overlays:** condensed all-caps labels, numeric telemetry, timers, status blocks, wireframe geometry, and large proposition/result text.
- **High-contrast command-center palette:** black/dark fields, amber/orange and red tactical graphics, pale technical text, plus sharp warning and approval/denial contrasts. Exact colors shift by shot, display, and continuity.
- **Countdown drama:** alerts, escalating status readouts, progressive takeover indicators, and a hard deadline are central to both the Ireul sequence and EoE intrusion.
- **Organic hardware beneath sterile UI:** clean geometric outer shells conceal wetware, dense tubes and wiring, maintenance corridors, and Naoko's handwritten annotations/back doors. This clash is more canonically distinctive than generic “CRT styling.”
- **Machine-readable judgment:** MAGI is usually encountered through terse answers, votes, probabilities, and system announcements—not three natural-language personalities chatting on screen.

### Not established by canon

- A specific amber = thinking, green = agree, red = disagree state machine;
- asynchronous terminal flicker representing cross-talk or rebuttals;
- visible token streams;
- the three cores debating in natural language;
- simultaneous “confidence equilibrium” lock-in;
- a central fourth synthesizer/controller.

All are valid UI inventions. For visual fidelity, label them as an interface interpretation and retain more of the terse machine verdict, typography, timed alert, and wetware/maintenance contrast.

## Continuity boundaries

### Original continuity

The TV series, followed by *The End of Evangelion*, supplies the personality mapping, Episode 6's qualified vote, Episode 11's majority-rule government, Episode 13's organic-computer/intrusion material, and EoE's distributed MAGI cyberattack and CASPER veto. This should be the project's primary lore baseline.

### Rebuild / New Theatrical Edition

The four Rebuild films are a separate retelling/continuity, not missing episodes of the TV story.[^rebuildofficial]

- MAGI exists and assists NERV operations in the early Rebuild films, but the films do not retell Episode 13: Ireul, the personality-transplant explanation, and the Naoko/CASPER reveal are omitted.
- After the fourteen-year jump, WILLE uses **MAGI Achiral** aboard the AAA Wunder. Screens identify Achiral units, and *3.0+1.0* shows them assisting the Paris operation. The hardware is depicted as banks of repeated small triple modules rather than only the original three monumental cores.[^achiral]
- The Rebuild films do not establish that MAGI Achiral contains Naoko's same scientist/mother/woman personality imprints. Applying the TV mapping to Achiral is therefore an assumption.
- Rebuild's monitor graphics are denser and more modern, but that is a production-design evolution, not proof of a different deliberation algorithm.

### Manga, games, novels, and other spin-offs

Yoshiyuki Sadamoto's manga, the *ANIMA* novels, games, and comedy/detective spin-offs are separate adaptations or continuities. They sometimes reuse or extend MAGI concepts, but additions from them should not be presented as TV-anime canon. This note intentionally excludes their mechanics from the core specification.

## Design implications for `magi-sim` (adaptation, not canon)

1. **Keep the three core names and minimal canonical labels; make the detailed prompts explicitly original.** A setup screen could say “Inspired by Naoko's scientist / mother / woman facets” and then disclose the project's operational lenses.
2. **Make “mother” and “woman” configurable or rename their product-facing lenses.** The 1995 gender essentialism is narratively important but weak as a universal AI policy taxonomy. Internally preserving BALTHASAR/CASPER while presenting “care/stewardship” and “desire/relational intuition” is clearer and less reductive.
3. **Use two decision policies:** ordinary motions use majority; high-impact or destructive motions require unanimity or explicit human confirmation. This is both safer and closer to the dramatic evidence.
4. **Retain `CONDITIONAL`.** It is one of the most directly canonical and useful mechanics. Conditions should remain attached to the final verdict rather than being flattened into yes/no.
5. **Make humans the authority.** Show MAGI as decision support: votes, dissent, conditions, risk estimate, and evidence. Avoid implying that three model outputs make a decision objectively safe.
6. **Treat visible debate as a “diagnostic trace.”** The anime shows outcomes, not a transcript, but a project needs something engaging. Present arguments as an interpretive visualization of internal conflict, perhaps with a mode that collapses into terse canon-like output.
7. **Prefer bounded rounds over uncontrolled asynchronous chatter.** The plan's reactive pub/sub design can loop, amplify errors, and spend tokens unpredictably. Parallel independent analyses → one cross-review → final ballot captures the gimmick with clearer convergence.
8. **Use action-specific quorum rules.** Put the quorum in the motion schema (`majority`, `unanimous`, `human_confirm`) instead of assuming every 2–1 result executes.
9. **Borrow the best visual contrast:** severe geometric overlays on top; messy organic/back-door maintenance detail underneath. A hidden “maintenance mode” with Naoko-style notes would feel more specific than generic neon cyberpunk.
10. **Call the security mode “Ireul intrusion” as fiction.** Simulate corrupted evidence, compromised cores, quorum degradation, and recovery; do not market it as a real prompt-injection defense unless it is actually tested as one.

## Source quality and uncertainties

The strongest evidence here is the animated primary text: Episodes 6, 11, 13, 21, and *The End of Evangelion*. Publicly linkable English scripts are fan translations and can differ from the official Netflix/GKIDS subtitles, especially around Special Command 582 and “protection 666.” Claims that depend on exact English technical wording are therefore marked cautiously. EvaGeeks is used as a navigational/secondary cross-check, not as canon; its MAGI page itself carries a cleanup warning.[^evageeks]

Authoritative English production documentation specifically about MAGI is scarce online. The official *Evangelion Chronicle* publication page confirms the licensed reference work but does not expose its MAGI entries.[^chronicle] The Rebuild distinction is supported by the official Evangelion site and the films themselves; MAGI Achiral construction details are best treated as screen observation corroborated by secondary documentation.

## Sources

[^tv6]: Primary work: *Neon Genesis Evangelion*, Episode 6, “Rei II” (1995), Operation Yashima briefing. Public reference transcript: [Animanga literal-translation script, lines 164–183](https://www.animanga.com/scripts/textesgb/eva6.html).
[^tv11]: Primary work: *Neon Genesis Evangelion*, Episode 11, “The Day Tokyo-3 Stood Still” (1995), opening city-government conversation. Public reference transcript: [Animanga Episode 11 script](https://www.animanga.com/scripts/textesgb/eva11.html).
[^tv13]: Primary work: *Neon Genesis Evangelion*, Episode 13, “Angel Invasion / Lilliputian Hitcher” (1995), especially the Ireul attack and Ritsuko's closing explanation. Public reference transcript: [Animanga Episode 13 script](https://www.animanga.com/scripts/textesgb/eva13.html).
[^tv13overview]: Secondary cross-check: [EvaGeeks Episode 13 synopsis](https://wiki.evageeks.org/Episode_13), which traces the infection from MELCHIOR through BALTHASAR and the counter-program through CASPER.
[^ep13translation]: The fan script renders the self-destruct announcement and Special Command 582 awkwardly and somewhat self-contradictorily; compare the sequence in the [Episode 13 transcript](https://www.animanga.com/scripts/textesgb/eva13.html) with the primary episode before implementing an exact rule.
[^eoe]: Primary work: *The End of Evangelion*, Episode 25′ “Air” (1997), the opening MAGI attack and Ritsuko/Gendo confrontation. Public reference translation: [Yasuyuki Sato's 1998 script](https://groups.google.com/g/rec.arts.anime.misc/c/DWIS7zsLGJg). See especially the attack dialogue and the displayed MELCHIOR/BALTHASAR/CASPER result.
[^filmbook]: Secondary synthesis citing the official Evangelion film books: [“Lilliputian Hitcher” references and production notes](https://en.wikipedia.org/wiki/Lilliputian_Hitcher).
[^matthew]: Primary religious text for the naming caveat: [Matthew 2:1–12](https://www.biblegateway.com/passage/?search=Matthew%202%3A1-12&version=NRSVUE), which calls the visitors magi but does not give the later traditional names.
[^rebuildofficial]: Official franchise source: [Evangelion official site](https://www.evangelion.jp/) for the New Theatrical Edition films; English distributor overview: [GKIDS, *Evangelion:3.0+1.11*](https://gkids.com/films/evangelion-30-111/).
[^achiral]: Primary works: *Evangelion: 3.0 You Can (Not) Redo* (2012) and *Evangelion: 3.0+1.0 Thrice Upon a Time* (2021), screen labels and Wunder/Paris sequences. Secondary screen-detail cross-check: [Evangelion Wiki, MAGI Rebuild history](https://evangelion.fandom.com/wiki/Magi#Rebuild_of_Evangelion_History). Treat unspoken construction inferences there as secondary.
[^evageeks]: Secondary reference: [EvaGeeks MAGI page](https://wiki.evageeks.org/Magi). Useful for episode pointers and branch locations, but currently marked by its editors as needing factual cleanup.
[^chronicle]: Official licensed publication listing: [TV Tokyo, *Evangelion Chronicle*](https://www.tv-tokyo.co.jp/anime/eva/).
