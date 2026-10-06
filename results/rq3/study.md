# Observability study over pre-existing repositories

Subjects analyzed: **58** (56 carry telemetry) across hosts: bitbucket, github, gitlab.
Total telemetry events scanned: 116420.

## Headline finding

Of the 14 telemetry-bearing repositories with at least one observed failure event, **10 (71.4%)** has at least one sampled failure event that cannot be joined to a recognized request/trace identifier from telemetry alone (i.e. cannot answer: _Why did this request fail (which trace/request was it)?_).

_Caveat: computed over sampled telemetry files/events and recognized correlation aliases only; evidence in external traces, unstructured messages, or unrecognized fields is not credited._

## Bug-class prevalence (among telemetry-bearing repositories)

| Bug class | Repos affected | Share | Findings | Question blocked |
| --- | ---: | ---: | ---: | --- |
| Failure without correlation id | 10 | 17.9% | 171 | Why did this request fail (which trace/request was it)? |
| Span without duration | 0 | 0.0% | 0 | How long did this operation take? |
| Failure without error evidence | 10 | 17.9% | 127 | What error caused this failure? |
| Raw sensitive value in telemetry | 10 | 17.9% | 110 | Is this telemetry safe to retain and share? |
| Unbounded metric label cardinality | 0 | 0.0% | 0 | Will this metric explode storage / cost as it scales? |
| Unclassified sensitive / tenant identifier | 19 | 33.9% | 1861 | Which fields carry regulated or tenant-scoped data? |

## Diagnosability score distribution

Over 56 telemetry-bearing repositories (0-100, higher is better):

- min **69**, p25 **98**, median **100**, p75 **100**, max **100**
- mean **97.643**

## Subjects

| Repository | Host | Events | Score | Verdict |
| --- | --- | ---: | ---: | --- |
| 5GR5/MCProtector@9d494a22efee | github | 26 | 100 | well-covered |
| AGENT17-tech/JARVIS-MKIII@626047b451a9 | github | 100 | 100 | well-covered |
| AmitabhainArunachala/mech-interp-latent-lab-phase1@02de8207b1a7 | github | 56190 | 100 | privacy-risky |
| Andert51/dt-QualityCtrl_ANN-FIS-GA@4dfc42761eaf | github | 54 | 100 | well-covered |
| Architit/LAM_Test_Agent@1d17163f50ac | github | 61 | 100 | well-covered |
| ArdurAI/mara@68fbfcb1261a | github | 69 | 100 | well-covered |
| BYU-PRISM/GEKKO@62206a086d91 | github | 606 | 100 | well-covered |
| Bbar0n234/learnflow-ai@562430744858 | github | 105 | 100 | well-covered |
| BhuvanChaithanya/Log_Triaging_Application@6aa7a7c2e282 | github | 318 | 100 | privacy-risky |
| BstWPY/WildGraphBench@c334bc806511 | github | 7615 | 100 | well-covered |
| CidLucas/platform@b431435575c4 | github | 13 | 100 | well-covered |
| Contingencyplana/high_command_ai_0@99d5753a581f | github | 456 | 99 | well-covered |
| DNYoussef/context-cascade@12bc124ee69b | github | 230 | 100 | well-covered |
| DavidAdolfoGomezUribe/chatbot_WS@582d637f09d9 | github | 46 | 100 | well-covered |
| Dicklesworthstone/franken_node@22abb3b17d5f | github | 6863 | 100 | privacy-risky |
| Keyhole-Koro/InsightifyCore@3a85106504fd | github | 38 | 100 | well-covered |
| Vannut97/web-refinery@c542937d21d4 | github | 9 | 87 | under-instrumented for incidents |
| adamiao/data-pipeline@2c4facf171b1 | github | 8 | 100 | well-covered |
| adinath-codes/ThreatZero@dd18d489a056 | github | 41 | 100 | well-covered |
| agentverus/agentverus-scanner@da63b5ccb5ef | github | 177 | 100 | well-covered |
| alexeyshockov/fingerscrossed@8ec726343d2f | github | 11 | 95 | under-instrumented for incidents |
| alexleighton/knowledge-bases@b7049b0d48a6 | github | 356 | 100 | well-covered |
| alextanhongpin/go-telemetry@ce3ec97e7305 | github | 5 | 100 | well-covered |
| allenai/noncompliance@25bf77cc6688 | github | 13784 | 100 | privacy-risky |
| almbayedahmad/medflux@d928bdbb43fc | github | 61 | 99 | under-instrumented for incidents |
| amirbahador-hub/Repository_Example@a2861892bf78 | github | 2 | 100 | well-covered |
| amsfwd/rootly-mcp-server@641391280d3f | github | 13 | 98 | privacy-risky |
| aniketpoojari/OmniDoc-QA-LLM-RAG@a9cc8e363769 | github | 24 | 100 | well-covered |
| api-evangelist/helicone@78cafe506c0b | github | 1 | 100 | well-covered |
| arefiva/mARCH-cli@0e46d181965d | github | 130 | 100 | well-covered |
| arolang/aro@b55585bdb844 | github | 522 | 99 | privacy-risky |
| aws-samples/sample-Agentic-Ai-Data-Operations@a07214f3ce25 | github | 55 | 90 | well-covered |
| aws-samples/sample-bedrock-migration-and-modernization-tools@64e54ba5d759 | github | 33 | 96 | well-covered |
| backrat13/Brave_New_Commune3@5a8f381ea49c | github | 367 | 100 | well-covered |
| barneyson55/incident-triage-toolkit@3cfbf69d0462 | github | 23 | 90 | privacy-risky |
| baz-scm/awesome-reviewers@eba0425fa059 | github | 1143 | 100 | privacy-risky |
| bb:atlassian_tutorial/helloworld@65d938f39f36 | bitbucket | 0 | - | no telemetry |
| beenlanced/python_project_uv_flask_webapp_demo@60645405fded | github | 31 | 100 | well-covered |
| benmoggee/sre-agent@80a561e50a60 | github | 108 | 93 | under-instrumented for incidents |
| bmdhodl/agent47@c3c3de7b7e84 | github | 586 | 96 | well-covered |
| bmislol/decision-intelligence-assistant@1e16231e97c8 | github | 7 | 69 | under-instrumented for incidents |
| bob-takuya/archi-site@e20a13a054ca | github | 389 | 100 | well-covered |
| bob-takuya/genshi-studio@024012008cd3 | github | 125 | 100 | well-covered |
| brant-ruan/vpss@796d7937de18 | github | 300 | 100 | well-covered |
| brevity1swos/agx@e25d76f0e24d | github | 30 | 98 | well-covered |
| brian14708/duron@a576b63dd2b7 | github | 59 | 99 | well-covered |
| c4r-dev/c4r-monorepo@0b3819c202d6 | github | 18607 | 98 | under-instrumented for incidents |
| cameronsjo/bosun@a18395dd7ead | github | 184 | 71 | privacy-risky |
| cdxgen/cdxgen@d67370778d66 | github | 4217 | 100 | well-covered |
| cerc-io/stack-orchestrator@fe7754001a14 | github | 65 | 100 | well-covered |
| comradesurendra/Argus@2923fca4b55c | github | 1 | 100 | well-covered |
| connachermurphy/llm-forecasting-aid-public@6ec3dc241beb | github | 4 | 100 | well-covered |
| cyrille-leclerc/my-shopping-cart@1e4440b1d7f2 | github | 53 | 95 | under-instrumented for incidents |
| darshan-sc/agentreplay@c900eb8646a3 | github | 4 | 100 | well-covered |
| dash0hq/dash0-cli@4fac994838b6 | github | 127 | 98 | under-instrumented for incidents |
| dloss/kelora@333e27eda618 | github | 1934 | 98 | privacy-risky |
| ecostratus/personal-operating-system-60d@97b1ec3fa0f3 | github | 34 | 100 | well-covered |
| gl:gitlab-examples/python-getting-started@4104c678f2a7 | gitlab | 0 | - | no telemetry |

