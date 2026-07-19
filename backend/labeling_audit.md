# Golden Dataset Labeling Audit

Scenario packs: **32**  |  Golden examples: **86**

Simulated labeler agreement: **52/86** (60.5%)

All labeling is `simulated=True` -- see AUTHORING_GUIDE.md before treating this rate as real inter-rater reliability.

## Coverage by category

- ambiguous_entity: 4
- multi_hop: 2
- negative: 12
- paraphrase: 32
- single_hop: 34
- temporal: 2

## Disagreements requiring real-labeler follow-up (34)

- **ge-002** (paraphrase): How many pricing plans do we offer customers now?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['17f4533f-7a50-5081-aa78-bd2838b681bc', '4b8d1cb9-f88d-5dc7-be65-bc677ff0de09']. Adjudicated to author-intended ground truth ['17f4533f-7a50-5081-aa78-bd2838b681bc'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-006** (paraphrase): How many pricing plans do we offer customers now?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['1427e05d-9454-5d1d-a602-967ce4f44e8d', '24172dc8-f418-584e-bd24-b814d8a59dc0']. Adjudicated to author-intended ground truth ['1427e05d-9454-5d1d-a602-967ce4f44e8d'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-010** (paraphrase): Who's running our candidate screening these days?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['d3d1754f-8389-5828-97a4-7273bf67dc1a']. Adjudicated to author-intended ground truth ['d3d1754f-8389-5828-97a4-7273bf67dc1a'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-012** (paraphrase): Who's running our candidate screening these days?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['f5c4b9c4-bf19-55e0-8ef0-b182bdcad28b']. Adjudicated to author-intended ground truth ['f5c4b9c4-bf19-55e0-8ef0-b182bdcad28b'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-014** (paraphrase): If the primary on-call doesn't respond, who gets paged next?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['d58f8310-71d8-5f18-b82a-50bfb616a432']. Adjudicated to author-intended ground truth ['d58f8310-71d8-5f18-b82a-50bfb616a432'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-016** (paraphrase): If the primary on-call doesn't respond, who gets paged next?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['259a5e95-63c4-57f9-8cbb-8950c68d28e5']. Adjudicated to author-intended ground truth ['259a5e95-63c4-57f9-8cbb-8950c68d28e5'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-018** (paraphrase): Can I ship code right before a big release goes out?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['7544462a-8fec-59e2-8059-122da7473a16']. Adjudicated to author-intended ground truth ['7544462a-8fec-59e2-8059-122da7473a16'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-020** (paraphrase): Can I ship code right before a big release goes out?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['28fe5907-827f-5d88-bfb3-100ce4e82245']. Adjudicated to author-intended ground truth ['28fe5907-827f-5d88-bfb3-100ce4e82245'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-022** (paraphrase): Postgres or Mongo -- what did we land on for the backend?
  - Labeler A (keyword overlap) flagged ['f0ab8759-3118-5562-a139-5c97c355a7b3']; Labeler B (domain/topic match) flagged ['6106a591-1393-51fb-9610-af744f072135', 'f0ab8759-3118-5562-a139-5c97c355a7b3']. Adjudicated to author-intended ground truth ['f0ab8759-3118-5562-a139-5c97c355a7b3'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-023** (ambiguous_entity): Between Postgres and Mongo, which one did we actually pick?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['6106a591-1393-51fb-9610-af744f072135', 'f0ab8759-3118-5562-a139-5c97c355a7b3']. Adjudicated to author-intended ground truth ['f0ab8759-3118-5562-a139-5c97c355a7b3'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-025** (paraphrase): Postgres or Mongo -- what did we land on for the backend?
  - Labeler A (keyword overlap) flagged ['caa44e05-e032-5baf-979c-d90579c1b44e']; Labeler B (domain/topic match) flagged ['51daed2e-f872-52c0-8c17-edd37fddd65b', 'caa44e05-e032-5baf-979c-d90579c1b44e']. Adjudicated to author-intended ground truth ['caa44e05-e032-5baf-979c-d90579c1b44e'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-026** (ambiguous_entity): Between Postgres and Mongo, which one did we actually pick?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['51daed2e-f872-52c0-8c17-edd37fddd65b', 'caa44e05-e032-5baf-979c-d90579c1b44e']. Adjudicated to author-intended ground truth ['caa44e05-e032-5baf-979c-d90579c1b44e'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-028** (paraphrase): What's the TTL on the unprocessed event data?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['8250bd78-95f9-5b8f-ba08-5575d1043243']. Adjudicated to author-intended ground truth ['8250bd78-95f9-5b8f-ba08-5575d1043243'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-030** (paraphrase): What's the TTL on the unprocessed event data?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['41ef0a6e-ff8a-51ce-a8a6-40600974bada']. Adjudicated to author-intended ground truth ['41ef0a6e-ff8a-51ce-a8a6-40600974bada'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-032** (paraphrase): What's our log archival window?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['dbcd2ffb-2959-50ca-8fa0-01bb37ab3657']. Adjudicated to author-intended ground truth ['dbcd2ffb-2959-50ca-8fa0-01bb37ab3657'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-034** (paraphrase): What's our log archival window?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['64f34bc7-0998-5912-be7a-f31b637eb11c']. Adjudicated to author-intended ground truth ['64f34bc7-0998-5912-be7a-f31b637eb11c'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-043** (single_hop): What's our process after a major incident?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['fcfcef2d-ebae-589f-aef3-3faff4a49441']. Adjudicated to author-intended ground truth ['fcfcef2d-ebae-589f-aef3-3faff4a49441'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-044** (paraphrase): Do we write anything up after a SEV1?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['fcfcef2d-ebae-589f-aef3-3faff4a49441']. Adjudicated to author-intended ground truth ['fcfcef2d-ebae-589f-aef3-3faff4a49441'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-045** (single_hop): What's our process after a major incident?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['8eabfe66-7818-5b2c-bbc4-8f68d912b418']. Adjudicated to author-intended ground truth ['8eabfe66-7818-5b2c-bbc4-8f68d912b418'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-046** (paraphrase): Do we write anything up after a SEV1?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['8eabfe66-7818-5b2c-bbc4-8f68d912b418']. Adjudicated to author-intended ground truth ['8eabfe66-7818-5b2c-bbc4-8f68d912b418'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-048** (paraphrase): What percentage of users see a brand-new feature on day one?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['7a434f0f-b4f0-5c2d-9d87-2be8a52609ec']. Adjudicated to author-intended ground truth ['7a434f0f-b4f0-5c2d-9d87-2be8a52609ec'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-050** (paraphrase): What percentage of users see a brand-new feature on day one?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['51cf5869-1982-5acb-a0b5-daf87031a1d2']. Adjudicated to author-intended ground truth ['51cf5869-1982-5acb-a0b5-daf87031a1d2'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-051** (single_hop): What's our refund policy for customers?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['4682b2e5-39ac-5e04-9c75-1025da238235']. Adjudicated to author-intended ground truth ['4682b2e5-39ac-5e04-9c75-1025da238235'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-053** (single_hop): What's our refund policy for customers?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['11c39d22-7c20-5d25-a8be-f90fb5084b22']. Adjudicated to author-intended ground truth ['11c39d22-7c20-5d25-a8be-f90fb5084b22'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-060** (paraphrase): Can someone on my own team approve my auth-related PR?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['8828e780-a0c4-5fe4-98d4-a85c70098359']. Adjudicated to author-intended ground truth ['8828e780-a0c4-5fe4-98d4-a85c70098359'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-062** (paraphrase): Can someone on my own team approve my auth-related PR?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['0757cecb-41fd-51cd-9321-56ff4a4de02c']. Adjudicated to author-intended ground truth ['0757cecb-41fd-51cd-9321-56ff4a4de02c'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-064** (paraphrase): Do contractors also need two-factor auth on our systems?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['89c2e663-0179-5477-a077-fe057fb4d6bf']. Adjudicated to author-intended ground truth ['89c2e663-0179-5477-a077-fe057fb4d6bf'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-066** (paraphrase): Do contractors also need two-factor auth on our systems?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['6b7fb84b-71ca-5d9a-a191-1b6647fcb534']. Adjudicated to author-intended ground truth ['6b7fb84b-71ca-5d9a-a191-1b6647fcb534'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-067** (single_hop): How often does the team have standup now?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['00e0bca4-bded-5194-9c8b-7d35585de1ec']. Adjudicated to author-intended ground truth ['00e0bca4-bded-5194-9c8b-7d35585de1ec'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-068** (paraphrase): Is standup a daily thing or not anymore?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['00e0bca4-bded-5194-9c8b-7d35585de1ec']. Adjudicated to author-intended ground truth ['00e0bca4-bded-5194-9c8b-7d35585de1ec'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-069** (single_hop): How often does the team have standup now?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['9f520fbc-36c7-5f42-a435-a32afdf4ffcc']. Adjudicated to author-intended ground truth ['9f520fbc-36c7-5f42-a435-a32afdf4ffcc'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-070** (paraphrase): Is standup a daily thing or not anymore?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['9f520fbc-36c7-5f42-a435-a32afdf4ffcc']. Adjudicated to author-intended ground truth ['9f520fbc-36c7-5f42-a435-a32afdf4ffcc'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-073** (single_hop): What database did Aurora Robotics pick for the warehouse arm firmware?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['6106a591-1393-51fb-9610-af744f072135', 'f0ab8759-3118-5562-a139-5c97c355a7b3']. Adjudicated to author-intended ground truth ['f0ab8759-3118-5562-a139-5c97c355a7b3'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.
- **ge-074** (single_hop): What database did Cobalt Analytics pick for the reporting service?
  - Labeler A (keyword overlap) flagged []; Labeler B (domain/topic match) flagged ['51daed2e-f872-52c0-8c17-edd37fddd65b', 'caa44e05-e032-5baf-979c-d90579c1b44e']. Adjudicated to author-intended ground truth ['caa44e05-e032-5baf-979c-d90579c1b44e'] -- keyword overlap is a known-weak signal for paraphrased or entity-ambiguous questions (see AUTHORING_GUIDE.md); real human review should re-check this case.