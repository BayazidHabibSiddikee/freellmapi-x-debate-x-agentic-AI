# Graph Report - .  (2026-08-26)

## Corpus Check
- Large corpus: 634 files · ~5,751,043 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 3186 nodes · 6023 edges · 243 communities (177 shown, 66 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 310 edges (avg confidence: 0.79)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Core Framework
- Core Framework
- Core Framework
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Service Module
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Feature Area
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Component Group
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster
- Small Cluster

## God Nodes (most connected - your core abstractions)
1. `getDb()` - 88 edges
2. `validateToken()` - 68 edges
3. `cn()` - 56 edges
4. `initDb()` - 39 edges
5. `migrateDbSchema()` - 37 edges
6. `Card` - 31 edges
7. `cn()` - 26 edges
8. `KnowledgeBase` - 26 edges
9. `createApp()` - 25 edges
10. `getUnifiedApiKey()` - 25 edges

## Surprising Connections (you probably didn't know these)
- `open_news()` --calls--> `talk2()`  [INFERRED]
  services/debate/tools/news.py → tools/vpa.py
- `code_task()` --calls--> `_cli_for()`  [INFERRED]
  agent-workspace/services/agent/tools_registry.py → services/agent/dispatcher.py
- `code_task()` --calls--> `_load_business_settings()`  [INFERRED]
  agent-workspace/services/agent/tools_registry.py → services/agent/dispatcher.py
- `code_task()` --calls--> `resolve_workspace()`  [INFERRED]
  agent-workspace/services/agent/tools_registry.py → services/agent/dispatcher.py
- `hybridSearch()` --indirect_call--> `score()`  [INFERRED]
  server/src/services/rag.ts → client/dev/mockApi.ts

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Tactical / Military Operative Community** — data_images_admiral_statura, data_images_thomas_barrett_card, data_images_alibaba_card, data_images_slave_john_card, data_images_sebastian_card, data_images_viktor_weber_card [INFERRED 0.85]
- **Anime-Style Character Portraits** — data_images_makima_card, data_images_misato_card, data_images_maya_card, data_images_little_sister_moon_card [INFERRED 0.90]
- **Dark-Themed Character Cards** — data_images_alibaba_card, data_images_hector_isekai_card, data_images_slave_john_card, data_images_sebastian_card, data_images_viktor_weber_card, data_images_admiral_statura [INFERRED 0.80]

## Communities (243 total, 66 thin omitted)

### Community 0 - "Core Framework"
Cohesion: 0.07
Nodes (37): FAISS, RecursiveCharacterTextSplitter, _hash(), load_or_build(), _compact(), context(), health(), KnowledgeBase (+29 more)

### Community 1 - "Core Framework"
Cohesion: 0.05
Nodes (50): REDACTIONS, sanitizeProviderErrorMessage(), JsonSchemaish, repairToolArguments(), toolSchemaMap(), assistantMessageSchema, chatCompletionSchema, contentBlockSchema (+42 more)

### Community 2 - "Core Framework"
Cohesion: 0.06
Nodes (40): GET(), GET(), GET(), Props, analyzeProfile(), ErrorAnalysis(), Props, Recommendation (+32 more)

### Community 3 - "Service Module"
Cohesion: 0.06
Nodes (46): _camofox_search(), create_integrated_hub_map(), _current_humidity(), _fallback_search(), _geocode(), get_flood_data(), get_route_data(), get_weather_data() (+38 more)

### Community 4 - "Service Module"
Cohesion: 0.12
Nodes (34): Avatar(), Character, tokenQS(), CharactersBrowser(), DispatchQueueCard(), JobRow, RunRow, STATUS_STYLE (+26 more)

### Community 5 - "Service Module"
Cohesion: 0.13
Nodes (31): express, express, createApp(), DB_PATH, __dirname, getUnifiedApiKey(), initDb(), isGatedApiPath() (+23 more)

### Community 6 - "Service Module"
Cohesion: 0.10
Nodes (47): Agent Dispatcher — Headless CLI Execution, CI Workflow — GitHub Actions Test & Build, code_task Grant — Executor-Level Permission Gate, Console AGENTS.md — Next.js Dev Instructions, Console CLAUDE.md — Developer Pointer, Console Copilot Instructions, Console README — Agentic OS Product Overview, Debate Engine — Character Roleplay Loop (+39 more)

### Community 7 - "Service Module"
Cohesion: 0.09
Nodes (43): add_dispatch_run(), add_message(), conn(), create_job(), create_team(), delete_team(), _ensure_jobs(), ensure_room() (+35 more)

### Community 8 - "Service Module"
Cohesion: 0.09
Nodes (42): backfillFallback(), createTables(), ensureApiKeysBaseUrlColumn(), ensureModelsKeyIdColumn(), ensureRequestKeyIdColumn(), ensureRequestRequestedModelColumn(), ensureRequestTtfbColumn(), ensureUnifiedKey() (+34 more)

### Community 9 - "Service Module"
Cohesion: 0.09
Nodes (40): Request, chat(), chat_page(), ChatRequest, delete_session(), download_dataset(), export_chat(), ExportRequest (+32 more)

### Community 10 - "Service Module"
Cohesion: 0.10
Nodes (38): parseBudget(), fallbackRouter, routingSchema, SORT_PRESETS, updateSchema, ChainRow, getAllPenalties(), getCustomWeights() (+30 more)

### Community 11 - "Service Module"
Cohesion: 0.10
Nodes (40): Exception, ToolError, add_message(), create_room(), db_status(), delete_room(), dispatch(), DispatchRequest (+32 more)

### Community 12 - "Service Module"
Cohesion: 0.12
Nodes (22): bot_session_file(), BotInstance, _legacy_run(), load_bots_config(), _load_settings(), make_bot(), poll_loop(), poll_once() (+14 more)

### Community 13 - "Service Module"
Cohesion: 0.12
Nodes (23): SourcesPage(), STATUSES, TONE_COLOR, formatRelative(), HermesStatusTile(), items, RunEvent, SkillRunner() (+15 more)

### Community 14 - "Service Module"
Cohesion: 0.13
Nodes (34): canMakeRequest(), canUseProvider(), canUseTokens(), clearPersistedCooldown(), COOLDOWN_DURATIONS, cooldownHits, cooldowns, countPersistedProviderRequests() (+26 more)

### Community 15 - "Service Module"
Cohesion: 0.08
Nodes (25): FloatingBar(), ModelsTabs(), Tooltip(), Popover(), PopoverContent(), PopoverTrigger(), Switch(), EmbeddingsData (+17 more)

### Community 16 - "Service Module"
Cohesion: 0.12
Nodes (28): GET(), PATCH(), PUT(), JournalEntryPage(), JournalPage(), SourceViewPage(), relativeDate(), WikiIndex() (+20 more)

### Community 17 - "Service Module"
Cohesion: 0.11
Nodes (34): log_event(), Any, services/agent/activity.py — structured activity log (logs/activity.jsonl).  Eve, _ask_reviewer(), capture_diff(), dispatch_spec(), dispatch_subtask(), _freellm_key() (+26 more)

### Community 18 - "Service Module"
Cohesion: 0.09
Nodes (35): code_task(), _cross_team_search_wrapper(), _detect_framework(), download_books(), install_raspberry_pi_imager(), list_raspberry_pi_imager_assets(), _publish_insight_wrapper(), Any (+27 more)

### Community 19 - "Service Module"
Cohesion: 0.10
Nodes (33): code_task(), _cross_team_search_wrapper(), _detect_framework(), download_books(), execute(), list_tools(), _publish_insight_wrapper(), Any (+25 more)

### Community 20 - "Service Module"
Cohesion: 0.07
Nodes (12): CSuiteCockpit(), Props, ClientCenter(), Props, Dashboard(), TabId, TABS, DeepIntel() (+4 more)

### Community 21 - "Service Module"
Cohesion: 0.06
Nodes (33): dependencies, better-sqlite3, description, devDependencies, electron, electron-builder, @electron/rebuild, esbuild (+25 more)

### Community 22 - "Service Module"
Cohesion: 0.09
Nodes (24): decrypt(), encrypt(), getEncryptionKey(), initEncryptionKey(), isDevFallbackAllowed(), maskKey(), missingKeyError(), parseHexKey() (+16 more)

### Community 23 - "Service Module"
Cohesion: 0.11
Nodes (31): bm25(), buildCorpus(), chunkText(), Corpus, corpusKey(), cosine(), DATA_DIR, decodeXmlEntities() (+23 more)

### Community 24 - "Service Module"
Cohesion: 0.10
Nodes (29): Body, DELETE(), GET(), POST(), fetchTeams(), GET(), BUSINESS_ROLES, Character (+21 more)

### Community 25 - "Service Module"
Cohesion: 0.16
Nodes (31): Process, build_menu(), collect_processes(), _confirm(), cpu_bar(), find_procs(), fmt_bytes(), fmt_uptime() (+23 more)

### Community 26 - "Service Module"
Cohesion: 0.12
Nodes (19): ThreadPoolExecutor, AgentReport, _call_agent_sync(), _call_with_fallback_sync(), IssueFixRequest, MasterAgent, agent_master.py  –  Async Multi-Agent Orchestrator =============================, Blocking call to one CLI agent.     Returns the output string, or "[ERROR] ..." (+11 more)

### Community 27 - "Service Module"
Cohesion: 0.12
Nodes (29): add_message(), conn(), create_team(), delete_team(), ensure_room(), get_messages(), init_schema(), list_rooms() (+21 more)

### Community 28 - "Service Module"
Cohesion: 0.13
Nodes (29): chunk_text(), embed_via_openrouter(), index_file(), init_db(), log(), main(), parse_frontmatter(), prune_missing() (+21 more)

### Community 29 - "Feature Area"
Cohesion: 0.09
Nodes (22): Document, merge_pdfs(), pdf_to_word(), Convert a .docx file to PDF.  Returns the path of the created PDF., Convert a PDF to .docx.  Returns the path of the created DOCX., Merge a list of PDF paths into one file., split_pdf(), text_to_pdf() (+14 more)

### Community 30 - "Feature Area"
Cohesion: 0.12
Nodes (22): extractImageUrl(), extractText(), extractToolCalls(), GEMINI_UNSUPPORTED_SCHEMA_KEYS, GeminiCandidate, GeminiPart, GeminiResponse, GoogleProvider (+14 more)

### Community 31 - "Feature Area"
Cohesion: 0.12
Nodes (19): GET(), GET(), MIME, POST(), Body, POST(), GET(), Params (+11 more)

### Community 32 - "Feature Area"
Cohesion: 0.09
Nodes (19): DEFAULT_DASHBOARD_ORIGINS, __dirname, getAllowedCorsOrigins(), regenerateUnifiedKey(), errorHandler(), createProxyRateLimiter(), parseLimit(), WindowState (+11 more)

### Community 33 - "Feature Area"
Cohesion: 0.15
Nodes (24): getSetting(), setSetting(), hasProvider(), maskKey(), statusPayload(), applyCatalog(), Catalog, catalogBaseUrl() (+16 more)

### Community 34 - "Feature Area"
Cohesion: 0.10
Nodes (28): _camofox_search(), create_integrated_hub_map(), _current_humidity(), _fallback_search(), _geocode(), get_flood_data(), get_route_data(), get_weather_data() (+20 more)

### Community 35 - "Feature Area"
Cohesion: 0.12
Nodes (21): AuthForm(), AuthGate(), AuthStatus, Input(), Label(), apiFetch(), BASE, clearToken() (+13 more)

### Community 36 - "Feature Area"
Cohesion: 0.16
Nodes (20): GET(), PackPage(), SkillRunPage(), SkillsIndexPage(), PackCard(), PackGlyph(), SkillCard(), getPack() (+12 more)

### Community 37 - "Feature Area"
Cohesion: 0.07
Nodes (27): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+19 more)

### Community 38 - "Feature Area"
Cohesion: 0.11
Nodes (13): GuessTheWordGame, Initialize the Guess the Word game, Update title with time and hints, Display introduction messages, Draw blank lines for each letter, Create attempt indicator circles, Update the score display, Update the incorrect guesses display (+5 more)

### Community 39 - "Feature Area"
Cohesion: 0.10
Nodes (17): Navbar(), navItems, queryClient, Button(), buttonVariants, DropdownMenu(), DropdownMenuCheckboxItem(), DropdownMenuContent() (+9 more)

### Community 40 - "Feature Area"
Cohesion: 0.08
Nodes (25): devDependencies, eslint, @eslint/js, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals, @types/node, @types/react (+17 more)

### Community 41 - "Feature Area"
Cohesion: 0.08
Nodes (24): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, jsx, lib, module, moduleDetection, moduleResolution (+16 more)

### Community 42 - "Feature Area"
Cohesion: 0.08
Nodes (25): @codemirror/state, @codemirror/theme-one-dark, @codemirror/view, dependencies, better-sqlite3, @codemirror/state, @codemirror/theme-one-dark, @codemirror/view (+17 more)

### Community 43 - "Feature Area"
Cohesion: 0.15
Nodes (20): getProvider(), distribution(), main(), pct(), printDistribution(), printScores(), Profile, PROFILES (+12 more)

### Community 44 - "Feature Area"
Cohesion: 0.13
Nodes (24): BlendshapeRequest, ExpressionRequest, health(), list_expressions(), MultiBlendshapeRequest, BaseModel, get, post (+16 more)

### Community 45 - "Feature Area"
Cohesion: 0.13
Nodes (18): HomePage(), loadActivity(), loadStandup(), loadVaultSparkline(), parseStandupSections(), ActivityFeed(), ActivityItem, KIND_COLOR (+10 more)

### Community 46 - "Feature Area"
Cohesion: 0.14
Nodes (15): configPath(), DesktopConfig, loadConfig(), saveConfig(), __dirname, createPopover(), __dirname, togglePopover() (+7 more)

### Community 47 - "Feature Area"
Cohesion: 0.15
Nodes (16): ensureSessionToken(), hashPassword(), verifyPassword(), requireAuth(), attempts, authRouter, credentialsSchema, createSession() (+8 more)

### Community 48 - "Feature Area"
Cohesion: 0.09
Nodes (23): autoprefixer, devDependencies, autoprefixer, eslint, eslint-config-next, postcss, tailwindcss, tailwindcss-animate (+15 more)

### Community 49 - "Feature Area"
Cohesion: 0.16
Nodes (19): Card(), CardAction(), CardContent(), CardDescription(), CardFooter(), CardHeader(), CardTitle(), SelectContent() (+11 more)

### Community 50 - "Feature Area"
Cohesion: 0.09
Nodes (22): dist, ES2022, src/__tests__, compilerOptions, declaration, declarationMap, esModuleInterop, forceConsistentCasingInFileNames (+14 more)

### Community 51 - "Feature Area"
Cohesion: 0.23
Nodes (10): CompletionOptions, parseRetryAfterMs(), providerHttpError, CloudflareProvider, CohereProvider, ChatCompletionChunk, ChatCompletionResponse, ChatMessage (+2 more)

### Community 52 - "Feature Area"
Cohesion: 0.11
Nodes (21): QuirkDefinition, SEVERITY_ORDER, AnalyticsSummary, ApiKey, ApiKeyCreate, ChatCompletionChoice, ChatCompletionRequest, ChatContent (+13 more)

### Community 53 - "Feature Area"
Cohesion: 0.23
Nodes (21): alarm(), alarm_instructions(), _clean(), coin(), email(), get_ticker_from_company(), know_all(), main() (+13 more)

### Community 54 - "Feature Area"
Cohesion: 0.14
Nodes (11): ConnectFourTwoPlayer, Check for 4 connected diagonally (/), Check for 4 connected diagonally (\\), Check if current move wins the game, Place a disc on the board, Check if game ended (win or tie), Switch between red and yellow, Handle mouse click on the board (+3 more)

### Community 55 - "Feature Area"
Cohesion: 0.13
Nodes (15): ArgumentParser, build_parser(), list_available_assets(), main(), List all assets in the latest Raspberry Pi Imager release.          Returns a li, Build the argument parser. Extracted for testability., CLI entrypoint. Returns the intended exit code.      Args:         argv:  Option, Tests for tools/raspberry_pi_imager.py  Uses unittest.mock so no network access (+7 more)

### Community 56 - "Feature Area"
Cohesion: 0.09
Nodes (21): aliases, components, hooks, lib, ui, utils, iconLibrary, menuAccent (+13 more)

### Community 57 - "Feature Area"
Cohesion: 0.09
Nodes (21): concurrently, dependencies, playwright-core, devDependencies, concurrently, name, private, scripts (+13 more)

### Community 58 - "Feature Area"
Cohesion: 0.13
Nodes (11): download_asset(), Download a single release asset with progress indication.      Args:         ass, FakeResponse, When output_dir is None, uses DEFAULT_DOWNLOAD_DIR., File exists but wrong size → re-download (line 161)., Downloaded size doesn't match expected → prints warning., Partial download should be cleaned up on failure., When output_dir is None, DEFAULT_DOWNLOAD_DIR is used (line 146). (+3 more)

### Community 59 - "Feature Area"
Cohesion: 0.10
Nodes (21): dependencies, clsx, @dnd-kit/core, @dnd-kit/utilities, @fontsource-variable/geist, @fontsource-variable/geist-mono, lucide-react, react-markdown (+13 more)

### Community 60 - "Feature Area"
Cohesion: 0.10
Nodes (20): compilerOptions, allowImportingTsExtensions, erasableSyntaxOnly, lib, module, moduleDetection, moduleResolution, noEmit (+12 more)

### Community 61 - "Feature Area"
Cohesion: 0.14
Nodes (15): GET(), POST(), POST(), POST(), CRON_JOBS_PATH, GATEWAY_STATE_PATH, hermes(), HermesCreateJobRequest (+7 more)

### Community 62 - "Feature Area"
Cohesion: 0.17
Nodes (15): listenWithScan(), ServerHandle, StartOptions, startServer(), tryListen(), __dirname, main(), resolveProvider() (+7 more)

### Community 63 - "Feature Area"
Cohesion: 0.12
Nodes (14): sendError(), sendOk(), BusinessConfig, businessRouter, CHARACTERS_FILE, CONFIG_FILE, DATA_DIR, DEFAULT_ROLES (+6 more)

### Community 64 - "Component Group"
Cohesion: 0.10
Nodes (20): Landing page hero — A LOCAL-FIRST AI COMPANY ON YOUR MACHINE, Product explanation panel — team debate workflow, Feature screenshot or UI section, Feature screenshot or UI section, Feature screenshot or UI section, Chapter 03 — Characters debate with cited evidence (Stripe migration debate), Continuation of Stripe billing debate — CTO and Engineer responses, Debate conclusion transitioning into Chapter 04 rules (+12 more)

### Community 65 - "Component Group"
Cohesion: 0.12
Nodes (20): SwordOffice app icon, Default Marin character avatar, Mobile app login/welcome screen, Mobile app secondary auth screen, Mobile app dashboard home, Mobile app feature list screen, Mobile app detail/content screen, Mobile app settings or profile screen (+12 more)

### Community 66 - "Component Group"
Cohesion: 0.18
Nodes (14): GET(), DELETE(), GET(), POST(), proxy(), GET(), POST(), ALLOWED_EXT (+6 more)

### Community 67 - "Component Group"
Cohesion: 0.16
Nodes (19): _cli_for(), Expand ~ and enforce the path stays under $HOME., resolve_workspace(), check_file_contains(), check_runs_printing(), compare(), Any, Path (+11 more)

### Community 68 - "Component Group"
Cohesion: 0.17
Nodes (14): Table(), TableBody(), TableCaption(), TableCell(), TableFooter(), TableHead(), TableHeader(), TableRow() (+6 more)

### Community 69 - "Component Group"
Cohesion: 0.11
Nodes (17): freellmKey(), queryDbSingle(), hasEnabledToolsModel(), hasEnabledVisionModel(), freshDb(), authJson, authJsonPath, crypto (+9 more)

### Community 70 - "Component Group"
Cohesion: 0.14
Nodes (17): appShapes, assets, BG, BLACK, chunk(), circle(), crc32(), CRC_TABLE (+9 more)

### Community 71 - "Component Group"
Cohesion: 0.13
Nodes (18): Console Dashboard — Main Landing View, Business Personas / Team Roster Screen, Dispatch Queue Card — Job Management, Business Settings Panel, Teams Management Interface, Telegram Bot Configuration, Transcript Ingestion Panel, Job Detail / Execution View (+10 more)

### Community 72 - "Component Group"
Cohesion: 0.18
Nodes (14): getDb(), logRequest(), getRequestAnalyticsRetentionConfig(), pruneRequestAnalytics(), readNonNegativeInt(), RequestAnalyticsRetentionConfig, RetentionDb, toSqliteTimestamp() (+6 more)

### Community 73 - "Component Group"
Cohesion: 0.20
Nodes (5): BaseProvider, providers, normalizeChoices(), OpenAICompatProvider, Platform

### Community 74 - "Component Group"
Cohesion: 0.18
Nodes (15): embeddingsRouter, updateSchema, callProvider(), EmbeddingModelRow, EmbeddingsError, EmbeddingsResult, estimateTokens(), getDefaultFamily() (+7 more)

### Community 75 - "Component Group"
Cohesion: 0.12
Nodes (16): aliases, components, hooks, lib, ui, utils, rsc, $schema (+8 more)

### Community 76 - "Component Group"
Cohesion: 0.12
Nodes (17): drizzle-kit, devDependencies, drizzle-kit, tsx, @types/better-sqlite3, @types/cors, @types/express, @types/node (+9 more)

### Community 77 - "Component Group"
Cohesion: 0.21
Nodes (14): Body, getCharacterList(), POST(), ROLE_DUTIES, rosterCharacterIdByName(), POST(), activeProject(), BusinessRole (+6 more)

### Community 78 - "Component Group"
Cohesion: 0.37
Nodes (14): ask_yn(), build_app(), check_prereqs(), copy_skills(), err(), finalize(), install_bridge(), main() (+6 more)

### Community 79 - "Component Group"
Cohesion: 0.37
Nodes (14): ensure_node_deps(), ensure_venv(), port_up(), run.sh script, show_status(), start_agent(), start_console(), start_debate() (+6 more)

### Community 80 - "Component Group"
Cohesion: 0.27
Nodes (14): callFromNamedJson(), containsDialectMarker(), couldBecomeDialectMarker(), DIALECT_MARKERS, extractBalancedJson(), isKnownTool(), parseFunctionTagDialect(), parseTokenDialect() (+6 more)

### Community 81 - "Component Group"
Cohesion: 0.23
Nodes (15): api_blendshape(), api_expression(), api_expressions_list(), api_health(), broadcast(), index(), main(), model() (+7 more)

### Community 82 - "Component Group"
Cohesion: 0.14
Nodes (15): Debate Service Banner Image, Debate Chat Interface Screenshot, Code Flow Feature Screenshot, Default Marin Avatar Placeholder, Generic User Avatar Placeholder, Map Feature Screenshot, Profile Page Screenshot, Quiz Feature Screenshot (+7 more)

### Community 83 - "Component Group"
Cohesion: 0.21
Nodes (12): Body, GET(), POST(), agent(), Body, freellmKey(), GET(), POST() (+4 more)

### Community 85 - "Component Group"
Cohesion: 0.13
Nodes (15): cors, dotenv, drizzle-orm, @freellmapi/shared, helmet, dependencies, better-sqlite3, cors (+7 more)

### Community 86 - "Component Group"
Cohesion: 0.13
Nodes (14): compilerOptions, esModuleInterop, forceConsistentCasingInFileNames, module, moduleResolution, noEmit, skipLibCheck, strict (+6 more)

### Community 87 - "Component Group"
Cohesion: 0.21
Nodes (14): cancel(), enqueue(), _finalize(), list_jobs(), _load_settings(), Any, services/agent/jobs.py — Phase: multi-project, parallel dispatch queue.  Turn a, Compute the job summary once every subtask has finished. (+6 more)

### Community 88 - "Component Group"
Cohesion: 0.16
Nodes (4): ConnectFour, Draw the Connect Four grid, Your exact 5-level strategy, Handle user click, then computer move

### Community 89 - "Component Group"
Cohesion: 0.14
Nodes (13): default, type, additionalProperties, description, properties, active_team_id, version, $schema (+5 more)

### Community 90 - "Component Group"
Cohesion: 0.23
Nodes (10): AutomationsPage(), WikiPage(), Badge(), BadgeProps, badgeVariants, ALLOWED, FrontmatterEditor(), Status (+2 more)

### Community 91 - "Component Group"
Cohesion: 0.14
Nodes (11): CHARACTERS, CHARACTERS_FILE, DATA_DIR, debateRouter, __dirname, EXPORTS_DIR, __filename, IMAGES_DIR (+3 more)

### Community 92 - "Component Group"
Cohesion: 0.22
Nodes (10): PageHeader(), Badge(), badgeVariants, CatalogSyncState, fmtDate(), fmtWhen(), LicenseStatus, PLAN_LABEL (+2 more)

### Community 93 - "Component Group"
Cohesion: 0.17
Nodes (13): properties, type, default, type, properties, type, items, type (+5 more)

### Community 94 - "Component Group"
Cohesion: 0.15
Nodes (13): active_project, allow_file_writes, dispatch_agent_default, dispatch_timeout_seconds, history_turns, max_tokens, model, rag_k (+5 more)

### Community 95 - "Component Group"
Cohesion: 0.19
Nodes (9): inter, metadata, mono, Nav(), ThemeProvider(), APP_LINKS, humanize(), SEGMENT_LABELS (+1 more)

### Community 96 - "Component Group"
Cohesion: 0.26
Nodes (11): getAllProviders(), arg(), dateVersion(), __dirname, flag(), main(), ModelRow, SUITE_ROOT (+3 more)

### Community 97 - "Component Group"
Cohesion: 0.21
Nodes (7): BanglaVoiceTranslator, draw(), Initialize the Bangla voice translator, Listen and recognize Bangla speech, Translate Bangla text to English, Generate simple replies based on English text, Take screenshot and draw it with turtle animation

### Community 98 - "Component Group"
Cohesion: 0.23
Nodes (7): Initialize the turtle translator, Draw the main interface, Convert text to speech and play it, Translate text to target language, Display a message on screen, Main translation loop, TurtleTranslator

### Community 99 - "Component Group"
Cohesion: 0.21
Nodes (10): components, Markdown, MarkdownInner(), MarkdownProps, ChatMessage, FallbackEntry, formatTime(), HistoryEntry (+2 more)

### Community 100 - "Component Group"
Cohesion: 0.24
Nodes (10): ALLOWED_KEYS, GET(), PATCH(), PatchableKeys, GET(), POST(), BusinessSettings, getSettings() (+2 more)

### Community 101 - "Component Group"
Cohesion: 0.17
Nodes (11): description, engines, node, homepage, license, name, private, repository (+3 more)

### Community 102 - "Component Group"
Cohesion: 0.27
Nodes (9): checkForUpdate(), currentVersion(), fetchLatestRelease(), readState(), semverGt(), STATE_PATH, UpdateInfo, UpdaterState (+1 more)

### Community 103 - "Component Group"
Cohesion: 0.27
Nodes (10): on_event, get_status(), monitor_whatsapp_dom(), get, Hook your custom Agentic AI logic here., root(), run_your_agentic_brain(), send_whatsapp_reply() (+2 more)

### Community 104 - "Component Group"
Cohesion: 0.40
Nodes (4): patch, detect_platform(), Auto-detect the appropriate Raspberry Pi Imager platform for this machine., TestDetectPlatform

### Community 105 - "Component Group"
Cohesion: 0.22
Nodes (10): handle(), Incoming, rl, textResult(), ToolDef, TOOLS, buildRagContext(), deleteDocument() (+2 more)

### Community 106 - "Component Group"
Cohesion: 0.35
Nodes (9): buildColleagueKnowledgeBlock(), countMemories(), forgetMemory(), getMemory(), listMemories(), memoriesAboutSubjects(), PersonaMemory, recordStatement() (+1 more)

### Community 107 - "Small Cluster"
Cohesion: 0.22
Nodes (6): activeWeights(), customWeights, MockModel, models, PRESETS, score()

### Community 108 - "Small Cluster"
Cohesion: 0.20
Nodes (9): name, private, scripts, build, dev, lint, preview, type (+1 more)

### Community 109 - "Small Cluster"
Cohesion: 0.20
Nodes (6): chatCompletion, EMPTY_RESULT, fakeProvider, GOOD_RESULT, post(), streamChatCompletion

### Community 110 - "Small Cluster"
Cohesion: 0.36
Nodes (9): cli_launch(), interactive(), is_available(), launch(), print_apps(), print_banner(), Non-interactive: swordfish.py <appname>, Check if the first word of a command is on PATH. (+1 more)

### Community 111 - "Small Cluster"
Cohesion: 0.31
Nodes (4): find_asset(), Find the download asset for *platform_key* within *release*.      For Linux .deb, When no asset matches the pattern, raise RuntimeError., TestFindAsset

### Community 112 - "Small Cluster"
Cohesion: 0.27
Nodes (5): get_latest_release(), Fetch the latest release metadata from the GitHub API.      Returns the parsed J, FakeApi, Fake .json() for API responses., TestGetLatestRelease

### Community 113 - "Small Cluster"
Cohesion: 0.28
Nodes (3): lerpRate(), mount(), parseColor()

### Community 114 - "Small Cluster"
Cohesion: 0.42
Nodes (7): ContentBlock, contentHasImage(), ContentTextBlock, contentToString(), flattenMessageContent(), messageHasImage(), normalizeOutboundContent()

### Community 115 - "Small Cluster"
Cohesion: 0.22
Nodes (3): request(), roleChunk, TOOLS

### Community 116 - "Small Cluster"
Cohesion: 0.31
Nodes (5): download_imager(), Download the latest Raspberry Pi Imager for the given platform.      Args:, When platform_key is 'auto' or None, detect_platform is called., The overwrite flag should be passed to download_asset., TestDownloadImager

### Community 117 - "Small Cluster"
Cohesion: 0.25
Nodes (4): _convert_temperature(), convert_unit(), programmer_calc(), Convert values between Dec, Bin, Hex, and Oct.

### Community 119 - "Small Cluster"
Cohesion: 0.39
Nodes (6): POST(), runDdgr(), runGogcli(), SearchOptions, SearchResult, webSearch()

### Community 120 - "Small Cluster"
Cohesion: 0.25
Nodes (8): AI Research Analyst Pro — Hero / Landing Section, AI Research Analyst Pro — Pricing & Comparison Section, AI Chat — Competitor Analysis Conversation, AI Chat — Structured Research Report Output, Reduced Thumbnail of mobile/16.png, Reduced Thumbnail of mobile/17.png, Reduced Thumbnail of mobile/18.png, Reduced Thumbnail of mobile/22.png

### Community 121 - "Small Cluster"
Cohesion: 0.43
Nodes (6): buildToolBlock(), parseToolCall(), ROLE_TOOL_GRANTS, TOOL_CATALOG, ToolDef, toolsForRole()

### Community 122 - "Small Cluster"
Cohesion: 0.25
Nodes (6): BROKEN_ARGS, chatCompletion, fakeProvider, post(), streamChatCompletion, UPDATE_PLAN_TOOL

### Community 123 - "Small Cluster"
Cohesion: 0.46
Nodes (7): analyze_impact(), fetch_all_news(), fetch_source(), main(), AsyncClient, Fetch and parse one RSS feed. Returns a list of news item dicts., send_telegram_notification()

### Community 124 - "Small Cluster"
Cohesion: 0.36
Nodes (5): analyze_image(), analyze_youtube(), get_rag_context(), preprocess_input(), Any

### Community 125 - "Small Cluster"
Cohesion: 0.50
Nodes (7): get_body_speech(), get_body_typed(), get_recipient(), listen_once(), main(), review_and_confirm(), send_email()

### Community 126 - "Small Cluster"
Cohesion: 0.25
Nodes (5): Additional tests to push coverage above 80%., A real HTTPError from raise_for_status becomes a RuntimeError., When cleanup itself fails with OSError, it's swallowed (line 203-204)., When the download fails AND a partial file exists, clean it up., TestAdditionalCoverage

### Community 127 - "Small Cluster"
Cohesion: 0.38
Nodes (4): SettingsPage(), FIELDS, SettingsForm(), searchToolsAvailable()

### Community 128 - "Small Cluster"
Cohesion: 0.48
Nodes (6): blob_to_vec(), cosine(), embed_query(), main(), Path, resolve_vault()

### Community 129 - "Small Cluster"
Cohesion: 0.29
Nodes (7): scripts, build, dev, export-catalog, start, test, test:watch

### Community 130 - "Small Cluster"
Cohesion: 0.38
Nodes (3): kill_camera(), open_camera(), take_photo()

### Community 133 - "Small Cluster"
Cohesion: 0.33
Nodes (5): compilerOptions, baseUrl, paths, files, references

### Community 134 - "Small Cluster"
Cohesion: 0.33
Nodes (6): required, teams, items, type, id, name

### Community 135 - "Small Cluster"
Cohesion: 0.60
Nodes (5): bad(), hdr(), ok(), doctor.sh script, warn()

### Community 136 - "Small Cluster"
Cohesion: 0.33
Nodes (6): scripts, build, dev, lint, start, typecheck

### Community 137 - "Small Cluster"
Cohesion: 0.40
Nodes (6): Simon Ghost Riley — Character Card, Evok — Character Card, Hector Isekai — Character Card, Sebastian — Character Card, SLAVE John — Character Card, Viktor Weber — Character Card

### Community 139 - "Small Cluster"
Cohesion: 0.33
Nodes (5): main, name, private, types, version

### Community 140 - "Small Cluster"
Cohesion: 0.40
Nodes (5): Admiral Statura Character, Elena Vasquez Character, Fallback Chain Architecture Diagram, Kim Hung Character, Mona Lanius Character

### Community 141 - "Small Cluster"
Cohesion: 0.40
Nodes (5): Analytics Dashboard Screenshot, Desktop Application Screenshot, API Keys Management Screenshot, Maya Character Card, Playground Interface Screenshot

### Community 142 - "Small Cluster"
Cohesion: 0.60
Nodes (4): embed_query(), main(), Path, resolve_vault()

### Community 143 - "Small Cluster"
Cohesion: 0.50
Nodes (4): detect_dim(), main(), Connection, Read one vector blob to determine the embedding dimensionality.

### Community 144 - "Small Cluster"
Cohesion: 0.40
Nodes (4): name, private, type, version

### Community 146 - "Small Cluster"
Cohesion: 0.67
Nodes (4): Little Sister Moon — Character Card, Makima — Character Card, Maya — Character Card, Misato — Character Card

### Community 148 - "Small Cluster"
Cohesion: 0.50
Nodes (4): Mobile Task Creation Dialog, Mobile Task Dashboard List, Reduced Thumbnail of mobile/15.png, Reduced Thumbnail of mobile/19.png

### Community 149 - "Small Cluster"
Cohesion: 0.50
Nodes (4): Mobile Analytics Dashboard, Mobile Notification Center, Reduced Thumbnail of mobile/20.png, Reduced Thumbnail of mobile/23.png

### Community 151 - "Small Cluster"
Cohesion: 0.67
Nodes (3): main(), Run each command, wait `delay` seconds, then kill it.     Returns list of result, run_sequence()

### Community 152 - "Small Cluster"
Cohesion: 0.83
Nodes (3): format_table(), get_ticker(), show_stock()

### Community 153 - "Small Cluster"
Cohesion: 0.67
Nodes (3): fetch_stock_price(), Inline stock price fetch — no GUI, returns data string for Marin., _resolve_ticker()

### Community 154 - "Small Cluster"
Cohesion: 0.67
Nodes (3): handle_request(), VRM Control MCP Server Exposes VRM avatar control as MCP tools for use with open, send_osc()

### Community 156 - "Small Cluster"
Cohesion: 1.00
Nodes (3): FreeLLMAPI Brand Favicon, SVG Icon Sprite Sheet, Vite Build Tool Logo

### Community 157 - "Small Cluster"
Cohesion: 0.67
Nodes (3): format, type, created_at

### Community 158 - "Small Cluster"
Cohesion: 0.67
Nodes (3): default, type, description

### Community 159 - "Small Cluster"
Cohesion: 0.67
Nodes (3): pattern, type, id

### Community 160 - "Small Cluster"
Cohesion: 0.67
Nodes (3): minLength, type, name

### Community 161 - "Small Cluster"
Cohesion: 0.67
Nodes (3): description, type, persona_overrides

### Community 162 - "Small Cluster"
Cohesion: 0.67
Nodes (3): Admiral Statura — Character Portrait, Kim Hung — Character Portrait, Thomas Barrett — Character Card

## Knowledge Gaps
- **665 isolated node(s):** `$schema`, `style`, `rsc`, `tsx`, `config` (+660 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **66 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Database` connect `Component Group` to `Core Framework`, `Feature Area`, `Feature Area`, `Service Module`, `Component Group`?**
  _High betweenness centrality (0.079) - this node is a cross-community bridge._
- **Why does `routeRequest()` connect `Feature Area` to `Core Framework`, `Component Group`, `Service Module`, `Component Group`, `Service Module`, `Service Module`, `Service Module`, `Feature Area`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `express` connect `Service Module` to `Small Cluster`, `Small Cluster`, `Small Cluster`, `Component Group`, `Service Module`, `Small Cluster`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `$schema`, `style`, `rsc` to the rest of the system?**
  _665 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Core Framework` be split into smaller, more focused modules?**
  _Cohesion score 0.06912442396313365 - nodes in this community are weakly interconnected._
- **Should `Core Framework` be split into smaller, more focused modules?**
  _Cohesion score 0.05191256830601093 - nodes in this community are weakly interconnected._
- **Should `Core Framework` be split into smaller, more focused modules?**
  _Cohesion score 0.05723905723905724 - nodes in this community are weakly interconnected._