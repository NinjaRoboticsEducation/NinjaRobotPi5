# Direct wiki manual links

The owner explicitly requested removing the four root navigation documents and
linking README directly to the full sources. This maintenance plan implements
that request, adjusts documentation checks, and corrects the existing navigation
claims using new immutable source versions. Robot contracts are unchanged.

The semantic correction below only updates manual-location wording, source
citations and corresponding AI review fingerprints.

```diff
Plan root-manual-links-260907: Owner-requested removal of root manual navigation: update source citations and the statements describing current manual locations.
Risk: medium

## write wiki/analyses/knowledge-limitations.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/analyses/knowledge-limitations.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/analyses/knowledge-limitations.md
@@ -15,10 +15,10 @@
   by: agent:codex
   at: '2026-09-06T22:53:22Z'
 sources:
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 - id: src-20260906-developmentguide
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
@@ -26,8 +26,8 @@
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:06Z'
-  target_hash: sha256:53ea6fa166dc93d13ecc7fb2c641f402d5f91f421f90d715b1c6959e2cd887fd
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:ea9662e7af60e4072aa16feb5b5414feae51b0b4b69f1dfc4c6e9331c8d1285b
   result: passed
   checks:
     source_support: passed
@@ -36,9 +36,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Knowledge limitations and verification
@@ -46,22 +46,22 @@
 Keyword search covers curated pages rather than all raw manual text. It does not
 follow citations for the caller. Try focused terms, read the overview, and open
 full sources. Search expiry flags, source fingerprints, and semantic review
-status are separate signals and must be checked together.[^src-20260906-knowledgeintegration]
+status are separate signals and must be checked together.[^src-20260907-knowledgeintegration]
 
 A missing result is an evidence gap, not proof a feature is absent. A page can be
 structurally valid while its explanation needs review. Current implementation
 fingerprints identify files needing knowledge review but cannot prove that prose
 is correct. AI-reviewed pages are not human-verified or hardware-tested pages.
 Editor adapters need actual session activation checks; a wiki-only workspace may
-not expose parent robot code.[^src-20260906-knowledgeintegration]
+not expose parent robot code.[^src-20260907-knowledgeintegration]
 
 The development guide's older quality-gate example uses narrower lint paths than
 the current root policy. Follow the root operating policy for the current full
 checks, and preserve the source's historical context rather than silently treating
-an older example as the complete current gate.[^src-20260906-developmentguide][^src-20260906-knowledgeintegration]
+an older example as the complete current gate.[^src-20260906-developmentguide][^src-20260907-knowledgeintegration]
 
 [Project overview](/overview.md).
 
 
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
 [^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

## write wiki/concepts/development-history.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-history.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-history.md
@@ -14,15 +14,15 @@
   by: agent:codex
   at: '2026-09-06T22:53:22Z'
 sources:
-- id: src-20260906-developmentlog
-  resource: urn:llmwiki:source:src-20260906-developmentlog
+- id: src-20260907-developmentlog
+  resource: urn:llmwiki:source:src-20260907-developmentlog
   title: DevelopmentLog.md
-  content_hash: sha256:9d2f7eb85695c830322023c4efa549e5d178030105a611468b003f4d8e0b1dd4
+  content_hash: sha256:da1ff98b3c0a33c61602ceca14e5f481c7f4f1e37e69460c7102e3257beb8f5c
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:06Z'
-  target_hash: sha256:533430a40d768b7825f9c5aeeab76f0ffc44eb37617c95eebc0f32548535b94e
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:fcbefcb58985d5fc1ec577bd2844efe82037f16868a917efa8668a2cf3cf6fc4
   result: passed
   checks:
     source_support: passed
@@ -31,9 +31,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Development history and decisions
@@ -41,14 +41,14 @@
 The development log retains dated records of implementation work, design
 choices, repairs, validation, and remaining work. Use a relevant dated entry
 when answering why a change was made. Read surrounding entries to determine
-whether a later decision superseded it.[^src-20260906-developmentlog]
+whether a later decision superseded it.[^src-20260907-developmentlog]
 
 Historical success reports refer to the recorded work and environment. They do
 not prove that today's checkout passes the same checks, or that a physical
 device was tested during a later documentation task. Cite the entry and state
-which current checks were actually run.[^src-20260906-developmentlog]
+which current checks were actually run.[^src-20260907-developmentlog]
 
 [Complete development log](/references/development-log.md).
 
 
-[^src-20260906-developmentlog]: DevelopmentLog.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentlog`.
+[^src-20260907-developmentlog]: DevelopmentLog.md, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-developmentlog`.

## write wiki/concepts/development-workflow.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-workflow.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/development-workflow.md
@@ -17,10 +17,10 @@
   by: agent:codex
   at: '2026-09-06T22:53:22Z'
 sources:
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 - id: src-20260906-developmentguide
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
@@ -28,8 +28,8 @@
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:06Z'
-  target_hash: sha256:c8f0369cc7f1a8c1247792dde4b93da093496772eaae92a5742d617ace70e4be
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:bd0acfbe3e2dd04f8011e991bed09941a8bde1b6f2d3686aec176e84bf869eb2
   result: passed
   checks:
     source_support: passed
@@ -38,9 +38,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Development and documentation workflow
@@ -54,17 +54,17 @@
 versions, topic pages, specifications and architecture guidance, then record
 the change and validation in the development log. If no documentation change is
 needed, record a specific reason. A new source version preserves the old source;
-current navigation and the knowledge map identify the active version.[^src-20260906-knowledgeintegration]
+current navigation and the knowledge map identify the active version.[^src-20260907-knowledgeintegration]
 
 Use the project's maintenance guide outside the knowledge bundle for exact
 commands. Prepare a semantic page plan, validate it, show the actual diff, and
 apply the approved plan with the wiki CLI. Review source support honestly and
 check current pointers, file fingerprints, links, indexes and review coverage.
-AI review is distinct from human verification.[^src-20260906-knowledgeintegration]
+AI review is distinct from human verification.[^src-20260907-knowledgeintegration]
 
 [Development guide](/references/development-guide.md) ·
 [History](/concepts/development-history.md).
 
 
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
 [^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

## write wiki/concepts/features-and-tools.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/features-and-tools.md
@@ -22,15 +22,15 @@
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
   content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:06Z'
-  target_hash: sha256:0fd2add29e1e2bb810876e9445514ea215b313c9df2e10dc4aa1e50b70a1b69a
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:2c8bea92e1d46f8376737f38a42fc20c1eececf180b22e43e92925ccbb696cb2
   result: passed
   checks:
     source_support: passed
@@ -39,9 +39,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Features, MCP tools, and Agent Skills
@@ -60,11 +60,11 @@
 Development wiki skills are a separate coding-tool workflow. This local knowledge
 integration does not install a robot MCP provider or change runtime interfaces.
 Use the existing robot tutorial for robot extensions and the wiki maintenance
-guide for developer knowledge updates.[^src-20260906-knowledgeintegration]
+guide for developer knowledge updates.[^src-20260907-knowledgeintegration]
 
 [MCP and skills tutorial](/references/mcp-skills-guide.md).
 
 
 [^src-20260906-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `migration-2026-09-07`; registered source `src-20260906-ninjarobot-mcp-skill`.
 [^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.

## write wiki/concepts/installation.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/installation.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/concepts/installation.md
@@ -19,15 +19,15 @@
   resource: urn:llmwiki:source:src-20260906-installationguide
   title: InstallationGuide.md
   content_hash: sha256:53f80c60feb139f0de547613bd14b8fcd87a2678ba5bf7dc75b1b2bccb1dc1c4
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:06Z'
-  target_hash: sha256:c89f536e16da0db4909428c180953ffc515f1af207c35041af7a5e8eb9d24ca1
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:9832068b6999b51d7251910c109749108aae7676a465d37a5b6549783d6b53a6
   result: passed
   checks:
     source_support: passed
@@ -36,9 +36,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Installation and hardware checks
@@ -55,10 +55,10 @@
 
 The developer wiki uses a separate Python environment. Its explicit setup and
 text-evidence preparation do not initialize robot devices. This integration
-contains no fresh Raspberry Pi hardware validation.[^src-20260906-knowledgeintegration]
+contains no fresh Raspberry Pi hardware validation.[^src-20260907-knowledgeintegration]
 
 [Open installation reference](/references/installation-guide.md).
 
 
 [^src-20260906-installationguide]: InstallationGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-installationguide`.
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.

## write wiki/overview.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/overview.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/overview.md
@@ -10,10 +10,10 @@
   by: agent:codex
   at: '2026-09-06T22:53:22Z'
 sources:
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 - id: src-20260906-developmentguide
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
@@ -21,8 +21,8 @@
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:05Z'
-  target_hash: sha256:82b4b2b09b867f0a069e05e4f7cf3bdee6bfcceaf4d79ec854857a8c998ebd69
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:a0bccc510d1a98ec6fef23caea760829945a7ae7f1a868c445c060dc46afe17d
   result: passed
   checks:
     source_support: passed
@@ -31,9 +31,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # NinjaRobotPi5 project overview
@@ -45,7 +45,7 @@
 The local wiki is the primary developer knowledge collection. Full manuals are
 versioned under raw source folders; outer README links and the project knowledge
 map identify the current versions. Read source records and limitations, then
-compare important claims with the current checkout before coding.[^src-20260906-knowledgeintegration]
+compare important claims with the current checkout before coding.[^src-20260907-knowledgeintegration]
 
 ## Browse project knowledge
 
@@ -61,5 +61,5 @@
 - [MCP and skills tutorial](references/mcp-skills-guide.md)
 
 
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.
 [^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.

## write wiki/references/development-guide.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-guide.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-guide.md
@@ -13,15 +13,15 @@
   resource: urn:llmwiki:source:src-20260906-developmentguide
   title: DevelopmentGuide.md
   content_hash: sha256:80e65e182e818957c7938c055a4327b3f4c79a6807b38c7b05580248f77eb38e
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:05Z'
-  target_hash: sha256:5c4426c3c590ca13735e31041528119c09a303e1b84cd8931d6c5286d741f068
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:73f6f4be5dc424cbd763be1529534f059d1406da47ac2f1cdabb701a4420e118
   result: passed
   checks:
     source_support: passed
@@ -30,9 +30,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Development guide
@@ -41,10 +41,10 @@
 
 Use the source identifier below to resolve the complete manual through the raw
 source catalog. The outer wiki README also links directly to the current full
-manual. Root filenames are navigation pages; source updates create new versions.
-Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+manual. Both READMEs link directly to full sources; updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]
 
 [Return to project overview](/overview.md).
 
 [^src-20260906-developmentguide]: DevelopmentGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentguide`.
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.

## write wiki/references/development-log.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-log.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/development-log.md
@@ -9,19 +9,19 @@
   by: agent:codex
   at: '2026-09-06T22:53:22Z'
 sources:
-- id: src-20260906-developmentlog
-  resource: urn:llmwiki:source:src-20260906-developmentlog
+- id: src-20260907-developmentlog
+  resource: urn:llmwiki:source:src-20260907-developmentlog
   title: DevelopmentLog.md
-  content_hash: sha256:9d2f7eb85695c830322023c4efa549e5d178030105a611468b003f4d8e0b1dd4
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+  content_hash: sha256:da1ff98b3c0a33c61602ceca14e5f481c7f4f1e37e69460c7102e3257beb8f5c
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:05Z'
-  target_hash: sha256:0ccac014213094eb54ed0ec7d0273f05d3a02b5cd7df7fc673cdee4439e4d44c
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:0edf9f4f0731b8cddae438d1c4856004f285e2bb6bfbb9ad96b8b383f7610205
   result: passed
   checks:
     source_support: passed
@@ -30,21 +30,21 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Development log
 
-The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20260906-developmentlog]
+The complete log preserves dated implementation decisions and validation reports. Historical test results describe their recorded checkout and date; they are not fresh verification.[^src-20260907-developmentlog]
 
 Use the source identifier below to resolve the complete manual through the raw
 source catalog. The outer wiki README also links directly to the current full
-manual. Root filenames are navigation pages; source updates create new versions.
-Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+manual. Both READMEs link directly to full sources; updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]
 
 [Return to project overview](/overview.md).
 
-[^src-20260906-developmentlog]: DevelopmentLog.md, source version `migration-2026-09-07`; registered source `src-20260906-developmentlog`.
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-developmentlog]: DevelopmentLog.md, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-developmentlog`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.

## write wiki/references/installation-guide.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/installation-guide.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/installation-guide.md
@@ -13,15 +13,15 @@
   resource: urn:llmwiki:source:src-20260906-installationguide
   title: InstallationGuide.md
   content_hash: sha256:53f80c60feb139f0de547613bd14b8fcd87a2678ba5bf7dc75b1b2bccb1dc1c4
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:05Z'
-  target_hash: sha256:6d71976836ad0e8f100f5d4855e46a9ae345e99c159045e15ddf144ed969aa38
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:3472d55b44cac9a5196a94282d70d6505d3c6e528eddfad9c5731a989f292cef
   result: passed
   checks:
     source_support: passed
@@ -30,9 +30,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # Installation guide
@@ -41,10 +41,10 @@
 
 Use the source identifier below to resolve the complete manual through the raw
 source catalog. The outer wiki README also links directly to the current full
-manual. Root filenames are navigation pages; source updates create new versions.
-Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+manual. Both READMEs link directly to full sources; updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]
 
 [Return to project overview](/overview.md).
 
 [^src-20260906-installationguide]: InstallationGuide.md, source version `migration-2026-09-07`; registered source `src-20260906-installationguide`.
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.

## write wiki/references/mcp-skills-guide.md
--- /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/mcp-skills-guide.md
+++ /home/rogerchang/NinjaRobotPi5/ninjarobot_pi5_wiki/wiki/references/mcp-skills-guide.md
@@ -13,15 +13,15 @@
   resource: urn:llmwiki:source:src-20260906-ninjarobot-mcp-skill
   title: NinjaRobot_MCP_Skill.md
   content_hash: sha256:df8076ccc2683b24b6752310558ce4e62828d54cee67f1102aae7196c0ee97bb
-- id: src-20260906-knowledgeintegration
-  resource: urn:llmwiki:source:src-20260906-knowledgeintegration
+- id: src-20260907-knowledgeintegration
+  resource: urn:llmwiki:source:src-20260907-knowledgeintegration
   title: Local knowledge integration evidence
-  content_hash: sha256:dabd8421a326cd9a56ad3f4d4f1d902f2e0e146897546a43e37d021e8f27c71f
+  content_hash: sha256:776049c49cbf2bf69cd0d59db1cbdfaaaea88ffa962f05548a604fec80071622
 semantic_review:
   version: 1
   performed_by: agent:codex
-  performed_at: '2026-09-06T22:54:05Z'
-  target_hash: sha256:a8cf576dc3e8de76cb55aff0636c1f5779837950046e3207ede4f555f8ca35a3
+  performed_at: '2026-09-07T00:45:19Z'
+  target_hash: sha256:cbdd4a7d3c84eabd5ccfb03bc1ffa2b38387b8dbc0eb4635220746b4e57ee8a1
   result: passed
   checks:
     source_support: passed
@@ -30,9 +30,9 @@
     claim_strength: passed
     visual_evidence: not_applicable
   notes:
-  - Reviewed this page against its listed manual sections and integration evidence.
-  - Claims describe documented contracts and knowledge workflow; current hardware
-    operation and interactive editor activation are not certified.
+  - Rechecked the navigation-only correction and updated source versions; other cited
+    explanations are unchanged.
+  - AI evidence review; no human verification or hardware test is claimed.
 ---
 
 # MCP and Agent Skills tutorial
@@ -41,10 +41,10 @@
 
 Use the source identifier below to resolve the complete manual through the raw
 source catalog. The outer wiki README also links directly to the current full
-manual. Root filenames are navigation pages; source updates create new versions.
-Read the relevant full section before acting on an abbreviated explanation.[^src-20260906-knowledgeintegration]
+manual. Both READMEs link directly to full sources; updates create new versions.
+Read the relevant full section before acting on an abbreviated explanation.[^src-20260907-knowledgeintegration]
 
 [Return to project overview](/overview.md).
 
 [^src-20260906-ninjarobot-mcp-skill]: NinjaRobot_MCP_Skill.md, source version `migration-2026-09-07`; registered source `src-20260906-ninjarobot-mcp-skill`.
-[^src-20260906-knowledgeintegration]: Local knowledge integration evidence, source version `integration-2026-09-07`; registered source `src-20260906-knowledgeintegration`.
+[^src-20260907-knowledgeintegration]: Local knowledge integration evidence, source version `root-manual-cleanup-2026-09-07`; registered source `src-20260907-knowledgeintegration`.

```
