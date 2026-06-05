import React, { useState } from 'react';
import FileUpload from './components/FileUpload';
import JdInput from './components/JdInput';
import Preview from './components/Preview';
import SkillMatchingModal from './components/SkillMatchingModal';
import VisualizationModal from './components/VisualizationModal';
import PdfProgressModal from './components/PdfProgressModal';
import ContextChatbot from './components/ContextChatbot';
import MultiResumeAnalysis from './components/MultiResumeAnalysis';
import LandingPage from './components/LandingPage';
import AuthGate from './components/AuthGate';
import ContextAnalysisPage from './components/ContextAnalysisPage';
import { useAuth } from './hooks/useAuth';
import { apiUrl } from './config/api';
import {
    ChevronDown,
    Menu,
    X,
    History,
    LayoutDashboard,
    FileText,
    BarChart3,
    Workflow,
    FileDown,
    CheckCircle2,
    Loader2,
    Circle,
    Microscope,
    Files,
    LogOut,
    BrainCircuit,
} from 'lucide-react';

function AppContent() {
    // Authentication variables mocked as null for database-free and offline operation
    const user = null;
    const token = null;
    const logout = () => {};
    const [resume, setResume] = useState(null);
    const [jdFile, setJdFile] = useState(null);
    const [jdText, setJdText] = useState("");
    const [domain, setDomain] = useState("software");
    const [extractedData, setExtractedData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [loadingTimeExceeded, setLoadingTimeExceeded] = useState(false);
    const [error, setError] = useState(null);
    const [isDomainOpen, setIsDomainOpen] = useState(false);
    const [activePage, setActivePage] = useState('landing');
    const [stageStep, setStageStep] = useState(0);

    const [isGeneratingPDF, setIsGeneratingPDF] = useState(false);
    const [pdfProgress, setPdfProgress] = useState(0);
    const [showPdfProgress, setShowPdfProgress] = useState(false);
    const [pdfProgressLabel, setPdfProgressLabel] = useState('Preparing report data...');
    const [isHighlightEnabled, setIsHighlightEnabled] = useState(false);
    const [evidencePersona, setEvidencePersona] = useState('hr');
    const [viewportWidth, setViewportWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1280);
    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const [analysisHistory, setAnalysisHistory] = useState([]);
    const [historyLoading, setHistoryLoading] = useState(false);
    const [historyError, setHistoryError] = useState(null);

    const isAdmin = String(user?.role || '').toLowerCase() === 'admin';

    const isCompactScreen = viewportWidth <= 700;

    React.useEffect(() => {
        const handleResize = () => setViewportWidth(window.innerWidth);
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    React.useEffect(() => {
        if (!isCompactScreen) {
            setIsSidebarOpen(false);
        }
    }, [isCompactScreen]);

    React.useEffect(() => {
        if (!isAdmin && activePage === 'analysis-history') {
            setActivePage('workspace');
        }
    }, [isAdmin, activePage]);

    React.useEffect(() => {
        if (activePage !== 'analysis-history' || !isAdmin || !token) {
            return;
        }

        let isMounted = true;

        const fetchAnalysisHistory = async () => {
            setHistoryLoading(true);
            setHistoryError(null);

            try {
                const response = await fetch(apiUrl('/auth/admin/analysis-history?limit=200'), {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                });

                if (!response.ok) {
                    const err = await response.json().catch(() => ({}));
                    throw new Error(err.detail || 'Failed to load analysis history');
                }

                const payload = await response.json();
                if (isMounted) {
                    setAnalysisHistory(Array.isArray(payload?.records) ? payload.records : []);
                }
            } catch (err) {
                if (isMounted) {
                    setHistoryError(err?.message || 'Unable to load analysis history right now.');
                    setAnalysisHistory([]);
                }
            } finally {
                if (isMounted) {
                    setHistoryLoading(false);
                }
            }
        };

        fetchAnalysisHistory();

        return () => {
            isMounted = false;
        };
    }, [activePage, isAdmin, token]);

    // Domain Options
    const domainOptions = [
        { id: 'software', label: 'Software Engineering', icon: '💻' },
        { id: 'medical', label: 'Medical & Healthcare', icon: '🏥' },
        { id: 'electrical', label: 'Electrical Engineering', icon: '⚡' },
        { id: 'marketing', label: 'Marketing & Sales', icon: '📢' },
        { id: 'finance', label: 'Finance & Banking', icon: '💰' },
        { id: 'human_resources', label: 'Human Resources', icon: '👥' }
    ];

    // Clear extraction results if inputs change
    React.useEffect(() => {
        setExtractedData(null);
        if (!loading) {
            setStageStep(0);
        }
    }, [resume, jdFile, jdText, domain]);

    React.useEffect(() => {
        const hasInputs = !!resume && (!!jdFile || !!jdText.trim());
        if (!loading && !extractedData) {
            setStageStep(hasInputs ? 1 : 0);
        }
    }, [resume, jdFile, jdText, loading, extractedData]);

    React.useEffect(() => {
        let timer;
        if (loading) {
            setLoadingTimeExceeded(false);
            timer = setTimeout(() => {
                setLoadingTimeExceeded(true);
            }, 40000);
        } else {
            setLoadingTimeExceeded(false);
        }
        return () => clearTimeout(timer);
    }, [loading]);

    const handleExtract = async () => {
        setLoading(true);
        setError(null);
        setExtractedData(null);
        setStageStep(2);

        const formData = new FormData();
        formData.append('resume', resume);
        formData.append('domain', domain);

        if (jdFile) {
            formData.append('job_description_file', jdFile);
        } else if (jdText) {
            formData.append('job_description_text', jdText);
        } else {
            setError("Please provide a Job Description (File or Text)");
            setLoading(false);
            return;
        }

        try {
            const headers = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(apiUrl('/extract'), {
                method: 'POST',
                headers,
                body: formData,
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Extraction failed");
            }

            const data = await response.json();
            setExtractedData(data);
            setActivePage('workspace');
            setStageStep(3);
        } catch (err) {
            setError(err.message);
            setStageStep(1);
        } finally {
            setLoading(false);
        }
    };

    const handleExportPdf = async () => {
        if (!extractedData || isGeneratingPDF) return;

        // ── Phase schedule: label, target%, duration (ms) ─────────────────
        const PHASES = [
            { label: 'Preparing analysis data…',        pct: 12,  ms: 700  },
            { label: 'Initialising chart engine…',       pct: 28,  ms: 1200 },
            { label: 'Rendering gauge & radar charts…',  pct: 44,  ms: 1400 },
            { label: 'Building visualisation panels…',   pct: 58,  ms: 1200 },
            { label: 'Composing match ledger table…',    pct: 70,  ms: 1000 },
            { label: 'Finalising page layout…',          pct: 82,  ms: 1000 },
            { label: 'Compiling PDF document…',          pct: 90,  ms: 800  },
            { label: 'Almost done — preparing download…',pct: 96,  ms: 600  },
        ];

        const wait = (ms) => new Promise((res) => setTimeout(res, ms));

        setIsGeneratingPDF(true);
        setShowPdfProgress(true);
        setPdfProgress(0);
        setPdfProgressLabel('Starting…');

        // Start animated phase progression (runs concurrently with fetch)
        const animatePhases = async () => {
            for (const phase of PHASES) {
                setPdfProgress(phase.pct);
                setPdfProgressLabel(phase.label);
                await wait(phase.ms);
            }
        };

        try {
            // Kick off UI animation and fetch simultaneously
            const [, response] = await Promise.all([
                animatePhases(),
                fetch(apiUrl('/export-pdf'), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(extractedData),
                }),
            ]);

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Server error ${response.status}`);
            }

            // Complete progress arc
            setPdfProgress(100);
            setPdfProgressLabel('Report ready — downloading…');

            const blob = await response.blob();
            const domain  = extractedData?.domain || 'general';
            const ts      = new Date().toISOString().slice(0, 10);
            const url     = URL.createObjectURL(blob);
            const anchor  = document.createElement('a');
            anchor.href   = url;
            anchor.download = `Resume_Analysis_${domain}_${ts}.pdf`;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            URL.revokeObjectURL(url);

            await wait(900);
        } catch (err) {
            console.error('PDF generation error:', err);
            setError(err?.message || 'Failed to generate PDF. Please try again.');
        } finally {
            setIsGeneratingPDF(false);
            setTimeout(() => {
                setShowPdfProgress(false);
                setPdfProgress(0);
                setPdfProgressLabel('Preparing report data…');
            }, 500);
        }
    };

    const handleStartNewRun = () => {
        setResume(null);
        setJdFile(null);
        setJdText("");
        setExtractedData(null);
        setError(null);
        setLoading(false);
        setStageStep(0);
        setIsHighlightEnabled(false);
        setEvidencePersona('hr');
        setActivePage('workspace');
        setIsSidebarOpen(false);
        setShowPdfProgress(false);
        setPdfProgress(0);
        setPdfProgressLabel('Preparing report data...');
    };

    const isAnalyzeDisabled = !resume || (!jdFile && !jdText.trim()) || loading;
    const selectedDomain = domainOptions.find(opt => opt.id === domain);
    const navItems = [
        { id: 'workspace', label: 'File Upload', icon: LayoutDashboard },
        { id: 'documents', label: 'File Preview', icon: FileText },
        { id: 'skill-matching', label: 'Skill Matching', icon: Workflow },
        { id: 'evidence', label: 'AI Playground', icon: Microscope },
        { id: 'visuals', label: 'Visualization', icon: BarChart3 },
        { id: 'context-analysis', label: 'Context Analysis', icon: BrainCircuit },
    ];

    if (isAdmin) {
        navItems.push({ id: 'analysis-history', label: 'Analysis History', icon: History });
    }

    const matchedSkills = extractedData?.bert_results?.summary?.exact_match_count || 0;
    const semanticSkills = extractedData?.bert_results?.summary?.semantic_match_count || 0;
    const missingSkills = extractedData?.bert_results?.summary?.missing_skills_count || 0;
    const alignmentScore = extractedData?.bert_results?.summary?.overall_alignment_score || 0;
    const summary = extractedData?.bert_results?.summary || {};
    const skillPartition = extractedData?.bert_results?.skill_partition || {};
    const matchEvidence = extractedData?.bert_results?.match_evidence || [];
    const evidenceLayer = extractedData?.evidence_layer || {};
    const hrDecisionLayer = extractedData?.hr_decision_layer || {};
    const candidateDecisionLayer = extractedData?.candidate_decision_layer || {};
    const evidenceHeader = evidenceLayer?.page_header || {};
    const sourceHealth = evidenceLayer?.source_health || {};
    const decisionCards = Array.isArray(evidenceLayer?.decision_snapshot?.cards) ? evidenceLayer.decision_snapshot.cards : [];
    const roleFitNarrative = evidenceLayer?.role_fit_narrative || {};
    const candidateImprovementPlan = evidenceLayer?.candidate_improvement_plan || {};
    const qualityReliability = evidenceLayer?.quality_reliability || {};
    const aiEnrichment = extractedData?.ai_enrichment || {};
    const aiStatus = String(sourceHealth?.ai_status || aiEnrichment?.status || 'disabled').toLowerCase();
    const aiQuality = aiEnrichment?.quality || {};
    const aiTriageFromSchema = Array.isArray(evidenceLayer?.gap_prioritization?.items) ? evidenceLayer.gap_prioritization.items : [];
    const aiFocusFromSchema = [];
    const aiMappingsFromSchema = Array.isArray(evidenceLayer?.term_intelligence?.mappings) ? evidenceLayer.term_intelligence.mappings : [];
    const aiTriage = aiTriageFromSchema.length ? aiTriageFromSchema : (Array.isArray(aiEnrichment?.missing_skill_triage) ? aiEnrichment.missing_skill_triage : []);
    const aiInterviewFocus = aiFocusFromSchema.length ? aiFocusFromSchema : (Array.isArray(aiEnrichment?.interview_focus) ? aiEnrichment.interview_focus : []);
    const aiMappings = aiMappingsFromSchema.length ? aiMappingsFromSchema : (Array.isArray(aiEnrichment?.normalization?.mappings) ? aiEnrichment.normalization.mappings : []);
    const aiWarningsRaw = [
        ...(Array.isArray(sourceHealth?.warnings) ? sourceHealth.warnings : []),
        ...(Array.isArray(aiQuality?.warnings) ? aiQuality.warnings : []),
    ];
    const aiWarnings = Array.from(new Set(aiWarningsRaw.filter(Boolean).map((v) => String(v).trim()).filter(Boolean)));
    const aiCoveragePercent = Math.max(0, Math.min(100, Math.round((Number(sourceHealth?.ai_coverage_score ?? aiQuality?.coverage_score ?? 0)) * 100)));
    const aiRisk = String(sourceHealth?.hallucination_risk || aiQuality?.hallucination_risk || 'medium').toLowerCase();
    const aiModel = aiEnrichment?.model || 'Not available';

    // HR Decision Layer Extraction
    const hrExecutiveRec = hrDecisionLayer?.executive_recommendation || {};
    const hrSkillsAnalysis = hrDecisionLayer?.skills_requirement_analysis || {};
    const hrRiskAssessment = hrDecisionLayer?.risk_assessment || {};
    const hrQuickFacts = hrDecisionLayer?.quick_facts || {};
    const hrHiringReadiness = hrDecisionLayer?.hiring_readiness || {};

    // Candidate Decision Layer Extraction
    const candidateRoleFit = candidateDecisionLayer?.role_fit_assessment || {};
    const candidateEvidence = candidateDecisionLayer?.evidence_strength || {};
    const candidateGapRoadmap = candidateDecisionLayer?.gap_closure_roadmap || [];
    const candidateActionPlan = candidateDecisionLayer?.action_plan || {};
    const candidateCareer = candidateDecisionLayer?.career_insights || {};
    const candidateGuidance = candidateDecisionLayer?.overall_guidance || {};

    const getWordCount = (text) => {
        if (!text || !text.trim()) return 0;
        return text.trim().split(/\s+/).filter(Boolean).length;
    };

    const formatFileSize = (bytes) => {
        if (typeof bytes !== 'number' || Number.isNaN(bytes) || bytes <= 0) return 'Size N/A';
        const units = ['B', 'KB', 'MB', 'GB'];
        let size = bytes;
        let unitIndex = 0;
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex += 1;
        }
        return `${size.toFixed(size >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
    };

    const truncatePreview = (text, limit = 3200) => {
        if (!text) return 'No parsed content available yet.';
        return text.length > limit ? `${text.slice(0, limit)}...` : text;
    };

    const dedupeSkills = (arr = []) => {
        const seen = new Set();
        const out = [];
        arr.forEach((item) => {
            if (!item || typeof item !== 'string') return;
            const cleaned = item.trim();
            if (!cleaned) return;
            const key = cleaned.toLowerCase();
            if (!seen.has(key)) {
                seen.add(key);
                out.push(cleaned);
            }
        });
        return out;
    };

    const escapeRegex = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

    const toSkillEntries = (skills = [], category) => skills.map((skill) => ({
        skill,
        category,
    }));

    const buildHighlightedPreview = (text, skillEntries = []) => {
        if (!text) return 'No parsed content available yet.';
        if (!isHighlightEnabled || !skillEntries.length) return text;

        const orderedEntries = [...skillEntries]
            .filter((entry) => entry.skill && entry.skill.length > 1)
            .sort((a, b) => b.skill.length - a.skill.length);

        const ranges = [];
        const isOverlapping = (start, end) => ranges.some((range) => !(end <= range.start || start >= range.end));

        orderedEntries.forEach((entry) => {
            const pattern = new RegExp(`(^|[^A-Za-z0-9])(${escapeRegex(entry.skill)})(?=$|[^A-Za-z0-9])`, 'gi');
            let match;
            while ((match = pattern.exec(text)) !== null) {
                const start = match.index + (match[1]?.length || 0);
                const end = start + (match[2]?.length || 0);
                if (!isOverlapping(start, end)) {
                    ranges.push({
                        start,
                        end,
                        category: entry.category,
                    });
                }
            }
        });

        if (!ranges.length) return text;

        ranges.sort((a, b) => a.start - b.start);

        const nodes = [];
        let cursor = 0;
        ranges.forEach((range, idx) => {
            if (range.start > cursor) {
                nodes.push(text.slice(cursor, range.start));
            }
            nodes.push(
                <mark key={`${range.start}-${range.end}-${idx}`} className={`highlight-mark ${range.category}`}>
                    {text.slice(range.start, range.end)}
                </mark>
            );
            cursor = range.end;
        });

        if (cursor < text.length) {
            nodes.push(text.slice(cursor));
        }

        return nodes;
    };

    const exactSkills = dedupeSkills(skillPartition.exact_match || []);
    const strongSemantic = skillPartition.strong_semantic || [];
    const moderateSemantic = skillPartition.moderate_semantic || [];
    
    // Extract context analysis skills
    const contextValidations = extractedData?.context_analysis?.context_validations || [];
    const implicitContextSkills = dedupeSkills(contextValidations.filter(v => v.analysis_type === 'Implicit Match').map(v => v.skill_name));
    const validatedContextSkills = dedupeSkills(contextValidations.filter(v => v.analysis_type === 'Contextually Validated').map(v => v.skill_name));
    
    const matchSkills = dedupeSkills([...exactSkills]);
    const partialMatchSkills = dedupeSkills([...strongSemantic.map(item => item.skill), ...moderateSemantic.map(item => item.skill), ...strongSemantic.map(item => item.similar_to), ...moderateSemantic.map(item => item.similar_to), ...validatedContextSkills, ...implicitContextSkills]);
    
    const missingJdSkills = dedupeSkills((extractedData?.bert_results?.missing_from_resume || []).map((item) => item.skill));
    const actualGaps = dedupeSkills(contextValidations.filter(v => v.analysis_type === 'Actual Gap').map(v => v.skill_name));
    const allMissingSkills = dedupeSkills([...missingJdSkills, ...actualGaps]);
    
    const taxonomyExtraSkills = extractedData?.bert_results?.extra_resume_skills || [];
    const groqAdditionalSkills = contextValidations.filter(v => v.analysis_type === 'Additional Skill').map(v => v.skill_name);
    const allAdditionalSkills = dedupeSkills([...taxonomyExtraSkills, ...groqAdditionalSkills]);

    const jdHighlightEntries = [
        ...toSkillEntries(matchSkills, 'match'),
        ...toSkillEntries(partialMatchSkills, 'partial'),
        ...toSkillEntries(allMissingSkills, 'missing'), // Red in JD
    ];
    
    const resumeHighlightEntries = [
        ...toSkillEntries(matchSkills, 'match'),
        ...toSkillEntries(partialMatchSkills, 'partial'),
        ...toSkillEntries(allAdditionalSkills, 'additional'), // Purple in Resume
    ];

    const prettyMatchType = (value) => {
        if (value === 'exact') return 'Exact';
        if (value === 'strong_semantic') return 'Strong Semantic';
        if (value === 'moderate_semantic') return 'Moderate Semantic';
        if (value === 'missing') return 'Missing';
        return value || 'Unknown';
    };

    const compactSnippet = (value, limit = 210) => {
        if (!value || typeof value !== 'string') return 'No context captured.';
        const normalized = value.replace(/\s+/g, ' ').trim();
        if (!normalized) return 'No context captured.';
        return normalized.slice(0, limit);
    };

    const containsSkillTerm = (text, term) => {
        if (!text || !term || typeof text !== 'string' || typeof term !== 'string') return false;
        const pattern = new RegExp(`(^|[^A-Za-z0-9])${escapeRegex(term)}(?=$|[^A-Za-z0-9])`, 'i');
        return pattern.test(text);
    };

    const titleCaseToken = (value) => {
        if (!value || typeof value !== 'string') return 'Unknown';
        return value
            .split('_')
            .filter(Boolean)
            .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
            .join(' ');
    };

    const clampPercent = (value) => Math.max(0, Math.min(100, Math.round(Number(value) || 0)));

    const formatIsoTimestamp = (value) => {
        if (!value || typeof value !== 'string') return 'Not available';
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return 'Not available';
        return date.toLocaleString();
    };

    const toHumanLine = (value, prefix = '') => {
        const text = String(value || '').trim();
        if (!text) return '';
        const hasVerb = /\b(is|are|has|have|shows|demonstrates|indicates|suggests|requires|needs|lacks|proved|proven|improves|supports)\b/i.test(text);
        if (hasVerb || text.endsWith('.')) return text;
        return `${prefix}${text}.`;
    };

    const aiStatusMeta = (() => {
        if (aiStatus === 'success') return { label: 'Active', tone: 'success' };
        if (aiStatus === 'disabled') return { label: 'Disabled', tone: 'disabled' };
        if (aiStatus === 'failed') return { label: 'Failed', tone: 'failed' };
        return { label: titleCaseToken(aiStatus), tone: 'disabled' };
    })();

    const buildInlineHighlights = (text, terms = [], tone = 'neutral') => {
        if (!text || typeof text !== 'string') return 'No context captured.';

        const uniqueTerms = dedupeSkills(terms).filter((term) => term.length > 1);
        if (!uniqueTerms.length) return text;

        const orderedTerms = [...uniqueTerms].sort((a, b) => b.length - a.length);
        const ranges = [];
        const isOverlapping = (start, end) => ranges.some((range) => !(end <= range.start || start >= range.end));

        orderedTerms.forEach((term) => {
            const pattern = new RegExp(`(^|[^A-Za-z0-9])(${escapeRegex(term)})(?=$|[^A-Za-z0-9])`, 'gi');
            let match;
            while ((match = pattern.exec(text)) !== null) {
                const start = match.index + (match[1]?.length || 0);
                const end = start + (match[2]?.length || 0);
                if (!isOverlapping(start, end)) {
                    ranges.push({ start, end });
                }
            }
        });

        if (!ranges.length) return text;

        ranges.sort((a, b) => a.start - b.start);

        const nodes = [];
        let cursor = 0;
        ranges.forEach((range, idx) => {
            if (range.start > cursor) {
                nodes.push(text.slice(cursor, range.start));
            }

            nodes.push(
                <mark key={`${range.start}-${range.end}-${idx}`} className={`evidence-inline-mark ${tone}`}>
                    {text.slice(range.start, range.end)}
                </mark>
            );

            cursor = range.end;
        });

        if (cursor < text.length) {
            nodes.push(text.slice(cursor));
        }

        return nodes;
    };

    const renderMainContent = () => {
        if (activePage === 'evidence') {
            if (!extractedData) {
                return (
                    <section className="documents-panel evidence-layer-panel fade-in neo-panel">
                        <div className="results-empty">
                            Run an assessment to generate traceable match evidence with JD and resume context snippets.
                        </div>
                    </section>
                );
            }

            const evidenceRows = matchEvidence.slice(0, 24).map((item, idx) => {
                const matchType = item.match_type || 'neutral';
                const confidencePercent = Math.round((Number(item.confidence || 0)) * 100);
                const jdSnippet = compactSnippet(item.jd_snippet, 220);
                const resumeSnippet = compactSnippet(item.resume_snippet, 220);
                const highlightTone = matchType === 'exact'
                    ? 'exact'
                    : (matchType === 'strong_semantic' || matchType === 'moderate_semantic')
                        ? 'semantic'
                        : matchType;
                const highlightTerms = [item.skill, item.jd_skill, item.resume_skill].filter(Boolean);
                const isSemantic = matchType === 'strong_semantic' || matchType === 'moderate_semantic';
                const exactWordMissingInResume = !containsSkillTerm(resumeSnippet, item.skill || '');
                return {
                    id: `${item.skill || 'skill'}-${idx}`,
                    skill: item.skill || 'Unknown Skill',
                    matchType,
                    confidencePercent,
                    jdSkill: item.jd_skill || '-',
                    resumeSkill: item.resume_skill || '-',
                    jdSnippet,
                    resumeSnippet,
                    highlightTerms,
                    highlightTone,
                    isSemantic,
                    exactWordMissingInResume,
                };
            });

            const traceTabs = Array.isArray(evidenceLayer?.evidence_trace?.tabs) ? evidenceLayer.evidence_trace.tabs : [];
            const mapTraceRows = (tabId) => {
                const tab = traceTabs.find((entry) => entry?.tab_id === tabId);
                const rows = Array.isArray(tab?.rows) ? tab.rows : [];
                return rows.slice(0, 24).map((item, idx) => {
                    const matchType = item.match_type || (tabId === 'ready_signals' ? 'exact' : tabId === 'risk_gaps' ? 'missing' : 'strong_semantic');
                    const confidencePercent = Math.round((Number(item.confidence || 0)) * 100);
                    const jdSnippet = compactSnippet(item.jd_context, 220);
                    const resumeSnippet = compactSnippet(item.resume_context, 220);
                    const highlightTone = matchType === 'exact' ? 'exact' : (matchType === 'strong_semantic' || matchType === 'moderate_semantic' ? 'semantic' : matchType);
                    const isSemantic = matchType === 'strong_semantic' || matchType === 'moderate_semantic';
                    return {
                        id: `${item.skill || 'trace-skill'}-${idx}-${tabId}`,
                        skill: item.skill || 'Unknown Skill',
                        matchType,
                        confidencePercent,
                        jdSkill: item.skill || '-',
                        resumeSkill: item.skill || '-',
                        jdSnippet,
                        resumeSnippet,
                        highlightTerms: [item.skill].filter(Boolean),
                        highlightTone,
                        isSemantic,
                        exactWordMissingInResume: isSemantic,
                    };
                });
            };

            const readyRowsFromSchema = mapTraceRows('ready_signals');
            const validationRowsFromSchema = mapTraceRows('needs_validation');
            const riskRowsFromSchema = mapTraceRows('risk_gaps');

            // Deduplication logic: no skill appears in more than one lane
            const deduplicateLanes = (allRows) => {
                const seenSkills = new Set();
                const exactRows = [];
                const semanticRows = [];
                const missingRows = [];

                // Priority 1: Collect all exact matches (highest confidence)
                allRows.filter((row) => row.matchType === 'exact').forEach((row) => {
                    const skillKey = (row.skill || '').toLowerCase().trim();
                    if (skillKey && !seenSkills.has(skillKey)) {
                        exactRows.push(row);
                        seenSkills.add(skillKey);
                    }
                });

                // Priority 2: Collect semantic matches (not already in exact)
                allRows.filter((row) => row.matchType === 'strong_semantic' || row.matchType === 'moderate_semantic').forEach((row) => {
                    const skillKey = (row.skill || '').toLowerCase().trim();
                    if (skillKey && !seenSkills.has(skillKey)) {
                        semanticRows.push(row);
                        seenSkills.add(skillKey);
                    }
                });

                // Priority 3: Collect missing skills (not already in exact or semantic)
                allRows.filter((row) => row.matchType === 'missing').forEach((row) => {
                    const skillKey = (row.skill || '').toLowerCase().trim();
                    if (skillKey && !seenSkills.has(skillKey)) {
                        missingRows.push(row);
                        seenSkills.add(skillKey);
                    }
                });

                return { exactRows, semanticRows, missingRows };
            };

            const { exactRows, semanticRows, missingRows } = readyRowsFromSchema.length || validationRowsFromSchema.length || riskRowsFromSchema.length
                ? {
                    exactRows: readyRowsFromSchema,
                    semanticRows: validationRowsFromSchema,
                    missingRows: riskRowsFromSchema,
                  }
                : deduplicateLanes(evidenceRows);

            const averageConfidence = evidenceRows.length
                ? Math.round(evidenceRows.reduce((acc, row) => acc + row.confidencePercent, 0) / evidenceRows.length)
                : 0;

            const hrVerdict = alignmentScore >= 75 && missingRows.length <= 4
                ? { title: 'Strong Shortlist', tone: 'positive', note: 'Candidate demonstrates strong role-fit with manageable gaps.' }
                : alignmentScore >= 55
                    ? { title: 'Interview with Focus Areas', tone: 'neutral', note: 'Candidate is viable, but interview must validate specific risk areas.' }
                    : { title: 'High Risk for Current Role', tone: 'risk', note: 'Current evidence suggests significant capability mismatch for this JD.' };

            const topStrengths = exactRows.slice(0, 4).map((row) => row.skill);
            const topRisks = missingRows.slice(0, 4).map((row) => row.skill);
            const semanticProbeRows = semanticRows.filter((row) => row.exactWordMissingInResume).slice(0, 3);
            const aiTopMappings = aiMappings.slice(0, 8);
            const fallbackRiskSkills = topRisks.length ? topRisks : missingJdSkills.slice(0, 4);
            const displayTriage = aiTriage.length ? aiTriage.slice(0, 6) : fallbackRiskSkills.map((skill, index) => ({
                skill,
                priority: index < 2 ? 'role_critical' : index < 4 ? 'important' : 'nice_to_have',
                impact: index < 2 ? 'high' : 'medium',
                trainability: index < 2 ? 'hard_to_train_fast' : 'trainable_mid_term',
                confidence: Math.max(0.45, 0.82 - (index * 0.08)),
                reason: `${skill} is currently a missing signal for this role and should be validated during screening.`,
            }));
            const displayInterviewFocus = aiInterviewFocus.length ? aiInterviewFocus.slice(0, 5) : semanticProbeRows.map((row) => ({
                topic: row.skill,
                question: `Walk me through a real delivery where you used ${row.skill}. What was your direct ownership and outcome?`,
                objective: `Confirm practical depth behind semantic match for ${row.skill}.`,
                expected_signal: 'Candidate provides measurable outcomes and concrete implementation details.',
                confidence: Math.max(0.45, Math.min(0.92, row.confidencePercent / 100)),
            }));

            const triageCriticalCount = displayTriage.filter((item) => String(item.priority || '').toLowerCase() === 'role_critical').length;
            const triageHighImpactCount = displayTriage.filter((item) => String(item.impact || '').toLowerCase() === 'high').length;
            const decisionConfidence = clampPercent((alignmentScore * 0.45) + (averageConfidence * 0.35) + (aiCoveragePercent * 0.2));
            const riskPressure = clampPercent((missingRows.length / Math.max(1, exactRows.length + missingRows.length)) * 100);
            const interviewReadiness = clampPercent((exactRows.length * 2.1) + (semanticRows.length * 1.2) - (missingRows.length * 1.3) + (displayInterviewFocus.length * 3) + (aiCoveragePercent * 0.15));
            const aiUpdatedAt = formatIsoTimestamp(evidenceLayer?.generated_at || aiEnrichment?.created_at);
            const sectionSourceBreakdown = Array.isArray(qualityReliability?.section_source_breakdown) ? qualityReliability.section_source_breakdown : [];
            const qualityNotes = Array.isArray(qualityReliability?.global_notes) ? qualityReliability.global_notes.filter(Boolean) : [];

            const extractEvidenceSkill = (item) => {
                if (!item) return '';
                if (typeof item === 'object') {
                    return String(item.skill || item.name || item.term || item.label || item.title || '').trim();
                }
                const cleaned = String(item || '')
                    .trim()
                    .replace(/^Candidate shows strong evidence in\s+/i, '')
                    .replace(/^A current hiring risk is missing evidence in\s+/i, '')
                    .replace(/^A current hiring risk is\s+/i, '')
                    .replace(/^Missing evidence in\s+/i, '')
                    .replace(/^Strong evidence in\s+/i, '')
                    .replace(/\s+can be improved in the short to mid term through targeted projects and mentorship\.?$/i, '')
                    .replace(/\.$/, '')
                    .trim();
                return cleaned;
            };

            const narrativeStrengthsRaw = Array.isArray(roleFitNarrative?.strengths) ? roleFitNarrative.strengths : [];
            const narrativeGapsRaw = Array.isArray(roleFitNarrative?.blocking_gaps) ? roleFitNarrative.blocking_gaps : [];
            const narrativeTrainableRaw = Array.isArray(roleFitNarrative?.trainable_in_30_60_days) ? roleFitNarrative.trainable_in_30_60_days : [];
            const narrativeStrengths = narrativeStrengthsRaw.length
                ? narrativeStrengthsRaw.map((item) => extractEvidenceSkill(item)).filter(Boolean)
                : topStrengths.slice(0, 3).filter(Boolean);
            const narrativeGaps = narrativeGapsRaw.length
                ? narrativeGapsRaw.map((item) => extractEvidenceSkill(item)).filter(Boolean)
                : topRisks.slice(0, 3).filter(Boolean);
            const narrativeTrainable = narrativeTrainableRaw.length
                ? narrativeTrainableRaw.map((item) => extractEvidenceSkill(item)).filter(Boolean)
                : displayTriage
                    .filter((item) => String(item.trainability || '').toLowerCase() !== 'hard_to_train_fast')
                    .slice(0, 3)
                    .map((item) => extractEvidenceSkill(item.skill))
                    .filter(Boolean);

            const finalRecommendation = roleFitNarrative?.final_recommendation || {};
            const recommendationDecision = titleCaseToken(finalRecommendation?.decision || hrVerdict.title);
            const recommendationRationale = finalRecommendation?.rationale || hrVerdict.note;

            const planItemsRaw = Array.isArray(candidateImprovementPlan?.items) ? candidateImprovementPlan.items : [];
            const candidatePlanItems = planItemsRaw.length ? planItemsRaw.slice(0, 4) : displayTriage.slice(0, 3).map((item, index) => ({
                skill: item.skill,
                priority_order: index + 1,
                what_to_build: `Build one project proving practical experience in ${item.skill} using role-relevant constraints.`,
                proof_artifacts: ['Project summary', 'Architecture notes', 'Outcome metrics'],
                expected_match_lift: Math.max(3, 9 - index),
            }));
            const planActionTemplates = [
                (skill) => `Start with one focused project where ${skill} is not optional but central to delivery decisions.`,
                (skill) => `Use your next practice sprint to apply ${skill} in a real workflow and document what changed because of it.`,
                (skill) => `Pick a practical scenario and show how you would use ${skill} from planning to final outcome.`,
                (skill) => `Build confidence in ${skill} by solving one problem end-to-end and capturing your reasoning clearly.`,
            ];
            const planCoachTemplates = [
                (skill) => `In interviews, speak in terms of choices, trade-offs, and outcomes when discussing ${skill}.`,
                (skill) => `Keep your explanation of ${skill} grounded in what you owned directly, not just team-level work.`,
                (skill) => `Show evidence of iteration in ${skill}: what failed first, what you changed, and what improved.`,
                (skill) => `Highlight one measurable impact linked to ${skill} so hiring teams can trust your depth quickly.`,
            ];
            const humanizedPlanItems = candidatePlanItems.map((item, idx) => {
                const skill = item.skill || 'this skill area';
                const templateLine = planActionTemplates[idx % planActionTemplates.length](skill);
                const rawBuild = String(item.what_to_build || '').trim();
                const actionLine = rawBuild && !/Build one project proving practical experience/i.test(rawBuild)
                    ? `${templateLine} Suggested focus: ${rawBuild}`
                    : templateLine;
                const coachLine = planCoachTemplates[idx % planCoachTemplates.length](skill);
                const artifactLine = Array.isArray(item.proof_artifacts) && item.proof_artifacts.length
                    ? item.proof_artifacts.join(', ')
                    : 'Project summary, architecture notes, measurable outcomes';
                return {
                    ...item,
                    actionLine,
                    coachLine,
                    artifactLine,
                };
            });

            const fitConfidence = clampPercent(Number(evidenceHeader?.fit_confidence ?? decisionConfidence));

            const evidenceDecisionOverview = (
                <>
                    <div className="evidence-section-kicker"><span className="evidence-emoji">📊</span>Decision Snapshot</div>
                    <section className="evidence-command-grid">
                        {decisionCards.length ? decisionCards.slice(0, 4).map((card, index) => (
                            <article key={card.id || `decision-${index}`} className={`evidence-command-card ${index === 0 ? 'primary' : index === 1 ? 'risk' : index === 2 ? 'neutral' : 'accent'}`}>
                                <p className="doc-label">{card.label || 'Decision Metric'}</p>
                                <p className="doc-value">{clampPercent(card.score)}%</p>
                                <p className="insight-subtext">{card.explanation || 'Evidence-derived decision metric.'}</p>
                            </article>
                        )) : (
                            <>
                                <article className="evidence-command-card primary">
                                    <p className="doc-label">Decision Confidence</p>
                                    <p className="doc-value">{decisionConfidence}%</p>
                                    <p className="insight-subtext">Composite score from alignment, evidence quality, and AI coverage.</p>
                                </article>
                                <article className="evidence-command-card risk">
                                    <p className="doc-label">Risk Pressure</p>
                                    <p className="doc-value">{riskPressure}%</p>
                                    <p className="insight-subtext">Higher values indicate stronger missing-skill pressure on hiring fit.</p>
                                </article>
                                <article className="evidence-command-card neutral">
                                    <p className="doc-label">Interview Readiness</p>
                                    <p className="doc-value">{interviewReadiness}%</p>
                                    <p className="insight-subtext">How prepared this profile is for structured panel interview evaluation.</p>
                                </article>
                                <article className="evidence-command-card accent">
                                    <p className="doc-label">Critical Gap Signals</p>
                                    <p className="doc-value">{triageCriticalCount} critical | {triageHighImpactCount} high impact</p>
                                    <p className="insight-subtext">Use this to prioritize technical screening and role-risk decisions.</p>
                                </article>
                            </>
                        )}
                    </section>
                </>
            );

            const pageGoalSection = (
                <section className="evidence-goal-banner">
                    <div className="evidence-goal-main">
                        <p className="doc-label"><span className="evidence-emoji">🎯</span>Page Goal + Fit Label</p>
                        <h4>{evidenceHeader?.fit_label || hrVerdict.title}</h4>
                        <p className="insight-subtext">{evidenceHeader?.one_line_summary || hrVerdict.note}</p>
                    </div>
                    <div className="evidence-goal-side">
                        <div className="evidence-fit-score">{fitConfidence}%</div>
                        <p className="evidence-fit-caption">Fit confidence</p>
                        <p className="evidence-fit-time">Updated: {aiUpdatedAt}</p>
                    </div>
                </section>
            );

            const evidenceOverviewShell = (
                <section className="evidence-overview-shell">
                    {pageGoalSection}
                    {evidenceDecisionOverview}
                </section>
            );

            const aiEnrichmentPanel = (
                <section className="evidence-ai-panel">
                    <div className="evidence-ai-header">
                        <div>
                            <p className="doc-label"><span className="evidence-emoji">🤖</span>AI Insight Studio</p>
                            <p className="doc-value">Recruiter-Grade Triage and Semantic Intelligence</p>
                            <p className="insight-subtext">Curated from AI enrichment and deterministic evidence so decisions remain meaningful and stable.</p>
                        </div>
                        <div className={`evidence-ai-status ${aiStatusMeta.tone}`}>
                            <Circle size={12} fill="currentColor" />
                            <span>{aiStatusMeta.label}</span>
                        </div>
                    </div>

                    <div className="evidence-ai-metrics">
                        <article className="evidence-ai-metric">
                            <p className="doc-label">Coverage</p>
                            <p className="doc-value">{aiCoveragePercent}%</p>
                        </article>
                        <article className="evidence-ai-metric">
                            <p className="doc-label">Hallucination Risk</p>
                            <p className="doc-value">{titleCaseToken(aiRisk)}</p>
                        </article>
                        <article className="evidence-ai-metric">
                            <p className="doc-label">Model</p>
                            <p className="doc-value">{aiModel}</p>
                        </article>
                        <article className="evidence-ai-metric">
                            <p className="doc-label">Last Updated</p>
                            <p className="doc-value">{aiUpdatedAt}</p>
                        </article>
                    </div>

                    <div className="evidence-ai-deep-grid">
                        <article className="document-card evidence-ai-card">
                            <p className="doc-label"><span className="evidence-emoji">🚨</span>Must-Have Gap Prioritization</p>
                            <div className="evidence-ai-chip-list">
                                {displayTriage.length ? displayTriage.map((item, index) => {
                                    const priority = titleCaseToken(item.priority || 'important');
                                    const impact = titleCaseToken(item.impact || 'medium');
                                    const trainability = titleCaseToken(item.trainability || 'trainable_mid_term');
                                    const conf = clampPercent((Number(item.confidence || 0)) * 100);
                                    return (
                                        <article className="evidence-ai-chip-card" key={`${item.skill || 'triage'}-${index}`}>
                                            <div className="evidence-ai-chip-top">
                                                <h5>{item.skill || 'Unspecified skill'}</h5>
                                                <span className="evidence-ai-chip-confidence">{conf}%</span>
                                            </div>
                                            <div className="evidence-ai-chip-tags">
                                                <span>{priority}</span>
                                                <span>{impact} impact</span>
                                                <span>{trainability}</span>
                                            </div>
                                            <p>{item.reason || 'No triage reason provided.'}</p>
                                        </article>
                                    );
                                }) : <p className="insight-subtext">No triage guidance available for this run.</p>}
                            </div>
                        </article>



                        <article className="document-card evidence-ai-card">
                            <p className="doc-label"><span className="evidence-emoji">🧠</span>Term Intelligence</p>
                            <div className="evidence-mapping-list">
                                {aiTopMappings.length ? aiTopMappings.map((item, index) => (
                                    <div className="evidence-mapping-row" key={`${item.source_term || 'mapping'}-${index}`}>
                                        <span className="mapping-source">{item.source_term || 'Unknown'}</span>
                                        <span className="mapping-arrow">→</span>
                                        <span className="mapping-target">{item.normalized_term || 'Unknown'}</span>
                                        <span className="mapping-confidence">{clampPercent((Number(item.confidence || 0)) * 100)}%</span>
                                    </div>
                                )) : <p className="insight-subtext">No semantic normalization mappings available.</p>}
                            </div>
                        </article>

                    </div>
                </section>
            );

            return (
                <section className="documents-panel evidence-layer-panel fade-in neo-panel">
                            <div className="evidence-viewmode-shell">
                                <div className="evidence-persona-selector">
                                    <p className="evidence-viewmode-title">View Mode</p>
                                    <div className="evidence-viewmode-buttons">
                                        <button
                                            onClick={() => setEvidencePersona('hr')}
                                            className={`evidence-viewmode-btn ${evidencePersona === 'hr' ? 'active' : ''}`}
                                        >
                                            HR View
                                        </button>
                                        <button
                                            onClick={() => setEvidencePersona('candidate')}
                                            className={`evidence-viewmode-btn ${evidencePersona === 'candidate' ? 'active' : ''}`}
                                        >
                                            Candidate View
                                        </button>
                                    </div>
                                </div>
                            </div>

                            {evidencePersona === 'hr' ? (
                                <>
                                    <div className="evidence-summary-row">
                                        <p className="insight-subtext"><span className="evidence-emoji">🎯</span>Executive Decision Summary - Hiring Readiness, Skills Gap Analysis & Risk Profile</p>
                                    </div>

                                    {/* ===== SECTION 1: EXECUTIVE RECOMMENDATION ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">✅</span>Hiring Recommendation</p>
                                            <div className="evidence-narrative-columns">
                                                <div style={{ background: 'linear-gradient(135deg, #eef1ff 0%, #f0f2ff 100%)', border: '1px solid #c7d2ff', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.5rem', color: '#5f67e8' }}>Decision</h5>
                                                    <p className="doc-value" style={{ marginTop: '0.2rem', fontSize: '1.1rem', fontWeight: '600' }}>
                                                        {hrExecutiveRec?.decision ? 
                                                            (hrExecutiveRec.decision === 'proceed' ? '✅ Proceed' :
                                                             hrExecutiveRec.decision === 'interview_with_focus' ? '🔍 Interview with Focus' :
                                                             hrExecutiveRec.decision === 'interview_with_conditions' ? '⚠️ Interview w/ Conditions' :
                                                             '🚫 High Risk')
                                                            : 'N/A'}
                                                    </p>
                                                    <p className="insight-subtext" style={{ marginTop: '0.3rem', fontStyle: 'italic' }}>
                                                        {hrExecutiveRec?.one_line_summary || 'No summary available'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%)', border: '1px solid #ddd6fe', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.5rem', color: '#7c3aed' }}>Decision Confidence</h5>
                                                    <p className="doc-value" style={{ marginTop: '0.2rem', fontSize: '1.3rem', fontWeight: '700' }}>
                                                        {hrExecutiveRec?.decision_confidence || 0}%
                                                    </p>
                                                    <p className="insight-subtext" style={{ marginTop: '0.3rem' }}>
                                                        High confidence in this recommendation
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #fff1f5 0%, #ffe4e6 100%)', border: '1px solid #fb7185', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.5rem', color: '#e11d48' }}>Key Drivers</h5>
                                                    <ul className="evidence-playbook-list" style={{ marginTop: '0.5rem', fontSize: '0.95rem' }}>
                                                        <li>{hrExecutiveRec?.key_drivers?.strengths || 'No strengths identified'}</li>
                                                        <li>{hrExecutiveRec?.key_drivers?.concern || 'No concerns identified'}</li>
                                                        <li>{hrExecutiveRec?.key_drivers?.trainable || 'No trainable gaps'}</li>
                                                    </ul>
                                                </div>
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== SECTION 2: SKILLS REQUIREMENT ANALYSIS ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">🎓</span>Skills Requirement Breakdown</p>
                                            <div className="evidence-narrative-columns">
                                                {/* Critical Must-Have */}
                                                <div style={{ background: 'linear-gradient(135deg, #fff1f5 0%, #ffe4e6 100%)', border: '1px solid #fb7185', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.4rem', color: '#e11d48' }}>Critical Must-Have</h5>
                                                    <p className="insight-subtext" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
                                                        {hrSkillsAnalysis?.critical_must_have?.summary || 'No critical skills defined'}
                                                    </p>
                                                    <ul style={{ marginTop: '0.4rem', paddingLeft: '1.2rem', fontSize: '0.95rem' }}>
                                                        {hrSkillsAnalysis?.critical_must_have?.gaps?.length > 0 ? (
                                                            <>
                                                                <li style={{ color: '#c7254e', fontWeight: '600' }}>❌ Gaps: {hrSkillsAnalysis.critical_must_have.gaps.join(', ')}</li>
                                                            </>
                                                        ) : (
                                                            <li style={{ color: '#28a745', fontWeight: '600' }}>✅ All matched</li>
                                                        )}
                                                    </ul>
                                                </div>

                                                {/* Important Skills */}
                                                <div style={{ background: 'linear-gradient(135deg, #fdf8f0 0%, #fef3c7 100%)', border: '1px solid #fcd34d', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.4rem', color: '#b45309' }}>Important Preferred</h5>
                                                    <p className="insight-subtext" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
                                                        {hrSkillsAnalysis?.important_strongly_preferred?.summary || 'No skills summary'}
                                                    </p>
                                                    <ul style={{ marginTop: '0.4rem', paddingLeft: '1.2rem', fontSize: '0.95rem' }}>
                                                        {hrSkillsAnalysis?.important_strongly_preferred?.gaps?.length > 0 ? (
                                                            <li style={{ color: '#856404' }}>⚠️ Gaps: {hrSkillsAnalysis.important_strongly_preferred.gaps.slice(0, 2).join(', ')}</li>
                                                        ) : (
                                                            <li style={{ color: '#28a745', fontWeight: '600' }}>✅ All matched</li>
                                                        )}
                                                        <li style={{ color: '#666', fontSize: '0.85rem' }}>Impact: Performance boost with these skills</li>
                                                    </ul>
                                                </div>

                                                {/* Nice-to-Have */}
                                                <div style={{ background: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)', border: '1px solid #6ee7b7', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.4rem', color: '#059669' }}>Nice-to-Have</h5>
                                                    <p className="insight-subtext" style={{ marginTop: '0.25rem', fontSize: '0.9rem' }}>
                                                        Differentiator skills that showcase depth
                                                    </p>
                                                    <ul style={{ marginTop: '0.4rem', paddingLeft: '1.2rem', fontSize: '0.95rem' }}>
                                                        <li style={{ color: '#059669', fontWeight: '600' }}>✅ {hrSkillsAnalysis?.nice_to_have?.matched?.length || 0} additional skills</li>
                                                        <li style={{ color: '#666', fontSize: '0.85rem' }}>Impact: Growth potential and differentiation</li>
                                                    </ul>
                                                </div>
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== SECTION 3: RISK & MITIGATION ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">⚠️</span>Risk Assessment & Mitigation</p>
                                            <div style={{ padding: '0rem' }}>
                                                {/* Risk Level Summary */}
                                                <div style={{ 
                                                    background: hrRiskAssessment?.overall_risk_level === 'high' ? 'linear-gradient(135deg, #fff1f5 0%, #ffe4e6 100%)' : hrRiskAssessment?.overall_risk_level === 'medium' ? 'linear-gradient(135deg, #fdf8f0 0%, #fef3c7 100%)' : 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)',
                                                    border: hrRiskAssessment?.overall_risk_level === 'high' ? '1px solid #fb7185' : hrRiskAssessment?.overall_risk_level === 'medium' ? '1px solid #fcd34d' : '1px solid #6ee7b7',
                                                    borderRadius: '12px',
                                                    padding: '0.8rem 1rem',
                                                    marginBottom: '0.8rem'
                                                }}>
                                                    <h5 style={{ marginBottom: '0.3rem' }}>Risk Level</h5>
                                                    <p className="doc-value" style={{ fontSize: '1.1rem', fontWeight: '600', marginTop: '0.2rem' }}>
                                                        {hrRiskAssessment?.overall_risk_level === 'high' ? '🔴 High Risk' :
                                                         hrRiskAssessment?.overall_risk_level === 'medium' ? '🟡 Medium Risk' :
                                                         '🟢 Low Risk'}
                                                    </p>
                                                    <p className="insight-subtext" style={{ marginTop: '0.3rem', fontSize: '0.9rem' }}>
                                                        Mitigation Timeline: {hrRiskAssessment?.mitigation_timeline?.replace(/_/g, ' ') || 'N/A'}
                                                    </p>
                                                </div>

                                                {/* Risk Factors */}
                                                {hrRiskAssessment?.risk_factors?.length > 0 ? (
                                                    <div style={{ padding: '0.5rem 0' }}>
                                                        <h5 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>Key Risk Factors</h5>
                                                        <div className="evidence-improvement-list">
                                                            {hrRiskAssessment.risk_factors.slice(0, 3).map((risk, idx) => (
                                                                <div key={`risk-${idx}`} style={{ background: 'linear-gradient(135deg, #f9f6ff 0%, #ede9fe 100%)', border: '1px solid #ddd6fe', borderRadius: '8px', padding: '0.6rem 0.8rem', marginBottom: '0.6rem' }}>
                                                                    <p style={{ fontWeight: '600', marginBottom: '0.3rem', fontSize: '0.95rem' }}>
                                                                        {idx + 1}. {risk?.factor || 'Risk factor'}
                                                                    </p>
                                                                    <ul style={{ paddingLeft: '1.2rem', fontSize: '0.9rem', margin: '0' }}>
                                                                        <li><strong>Severity:</strong> {risk?.severity || 'medium'}</li>
                                                                        <li><strong>Mitigation:</strong> {risk?.mitigation_strategy?.substring(0, 80) + '...' || 'N/A'}</li>
                                                                        <li><strong>Timeline:</strong> {risk?.trainability?.replace(/_/g, ' ') || 'N/A'}</li>
                                                                    </ul>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <p className="insight-subtext">✅ No significant risk factors identified.</p>
                                                )}
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== SECTION 4: QUICK FACTS & HIRING READINESS ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">📊</span>Quick Facts</p>
                                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                                                <div style={{ background: 'linear-gradient(135deg, #eef1ff 0%, #f0f2ff 100%)', padding: '0.7rem', borderRadius: '8px', border: '1px solid #c7d2ff' }}>
                                                    <p className="insight-subtext" style={{ fontSize: '0.85rem', marginBottom: '0.2rem' }}>Exact Matches</p>
                                                    <p className="doc-value" style={{ fontSize: '1.4rem', fontWeight: '700', color: '#5f67e8' }}>{hrQuickFacts?.exact_skill_matches || 0}</p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #fff1f5 0%, #ffe4e6 100%)', padding: '0.7rem', borderRadius: '8px', border: '1px solid #fb7185' }}>
                                                    <p className="insight-subtext" style={{ fontSize: '0.85rem', marginBottom: '0.2rem' }}>Skill Gaps</p>
                                                    <p className="doc-value" style={{ fontSize: '1.4rem', fontWeight: '700', color: '#e11d48' }}>{hrQuickFacts?.skill_gaps || 0}</p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #ecf7fc 0%, #cffafe 100%)', padding: '0.7rem', borderRadius: '8px', border: '1px solid #a5f3fc' }}>
                                                    <p className="insight-subtext" style={{ fontSize: '0.85rem', marginBottom: '0.2rem' }}>Overall Coverage</p>
                                                    <p className="doc-value" style={{ fontSize: '1.4rem', fontWeight: '700', color: '#06b6d4' }}>{hrQuickFacts?.overall_coverage || '0%'}</p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)', padding: '0.7rem', borderRadius: '8px', border: '1px solid #6ee7b7' }}>
                                                    <p className="insight-subtext" style={{ fontSize: '0.85rem', marginBottom: '0.2rem' }}>Role Alignment</p>
                                                    <p className="doc-value" style={{ fontSize: '1.4rem', fontWeight: '700', color: '#059669' }}>{hrQuickFacts?.role_alignment_score || 0}%</p>
                                                </div>
                                            </div>
                                        </article>

                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">🎤</span>Interview Readiness</p>
                                            <div style={{ padding: '0.5rem 0' }}>
                                                <div style={{ background: 'linear-gradient(135deg, #eef1ff 0%, #f0f2ff 100%)', border: '1px solid #c7d2ff', borderRadius: '8px', padding: '0.8rem', marginBottom: '0.6rem' }}>
                                                    <p style={{ fontWeight: '600', marginBottom: '0.3rem', color: '#5f67e8' }}>Can Conduct Interview</p>
                                                    <p className="doc-value" style={{ fontSize: '1.1rem' }}>
                                                        {hrHiringReadiness?.can_conduct_interview ? '✅ Yes' : '❌ No'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #fdf8f0 0%, #fef3c7 100%)', border: '1px solid #fcd34d', borderRadius: '8px', padding: '0.8rem', marginBottom: '0.6rem' }}>
                                                    <p style={{ fontWeight: '600', marginBottom: '0.3rem', color: '#b45309' }}>Onboarding Readiness</p>
                                                    <p className="doc-value" style={{ fontSize: '1.1rem' }}>
                                                        {hrHiringReadiness?.onboarding_readiness === 'high' ? '✅ High' :
                                                         hrHiringReadiness?.onboarding_readiness === 'medium' ? '⚠️ Medium' :
                                                         '🔴 Low'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)', border: '1px solid #6ee7b7', borderRadius: '8px', padding: '0.8rem' }}>
                                                    <p style={{ fontWeight: '600', marginBottom: '0.3rem', color: '#059669' }}>Pre-Interview Focus</p>
                                                    <p className="insight-subtext" style={{ marginTop: '0.3rem', fontSize: '0.9rem', lineHeight: '1.4' }}>
                                                        {hrHiringReadiness?.pre_interview_validation || 'No critical validations needed'}
                                                    </p>
                                                </div>
                                            </div>
                                        </article>
                                    </section>
                                </>
                            ) : (
                                <>
                                    <div className="evidence-summary-row">
                                        <p className="insight-subtext"><span className="evidence-emoji">🚀</span>Your Career Development Path - Role Readiness and Gap Closure Strategy</p>
                                    </div>

                                    {/* ===== SECTION 1: ROLE-FIT ASSESSMENT ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">📊</span>Your Role Readiness</p>
                                            <div className="evidence-narrative-columns">
                                                <div style={{ background: 'linear-gradient(135deg, #eef1ff 0%, #f0f2ff 100%)', border: '1px solid #c7d2ff', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.5rem', color: '#5f67e8' }}>Readiness Score</h5>
                                                    <p className="doc-value" style={{ marginTop: '0.2rem', fontSize: '1.6rem', fontWeight: '700', color: '#5f67e8' }}>
                                                        {candidateRoleFit?.readiness_score || 0}%
                                                    </p>
                                                    <p className="insight-subtext" style={{ marginTop: '0.3rem', fontSize: '0.9rem' }}>
                                                        {candidateRoleFit?.interpretation || 'Assessment not available'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #fdf8f0 0%, #fef3c7 100%)', border: '1px solid #fcd34d', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.5rem', color: '#b45309' }}>Interview Likelihood</h5>
                                                    <p className="doc-value" style={{ marginTop: '0.2rem', fontSize: '1.2rem', fontWeight: '600', color: '#b45309' }}>
                                                        {candidateRoleFit?.interview_likelihood === 'Very likely' ? '✨ Very Likely' :
                                                         candidateRoleFit?.interview_likelihood === 'Likely' ? '👍 Likely' :
                                                         candidateRoleFit?.interview_likelihood === 'Possible' ? '⚠️ Possible' :
                                                         '🤔 Unlikely'}
                                                    </p>
                                                    <p className="insight-subtext" style={{ marginTop: '0.3rem', fontSize: '0.9rem' }}>
                                                        {candidateRoleFit?.can_interview ? 'You can likely secure an interview' : 'Consider upskilling before applying'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #ecf7fc 0%, #cffafe 100%)', border: '1px solid #a5f3fc', borderRadius: '12px', padding: '0.9rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.5rem', color: '#06b6d4' }}>Skill Matches</h5>
                                                    <ul style={{ marginTop: '0.5rem', paddingLeft: '1.2rem', fontSize: '0.95rem', margin: '0' }}>
                                                        <li style={{ color: '#059669' }}>✅ {candidateRoleFit?.skills_breakdown?.matched_exact?.count || 0} exact matches</li>
                                                        <li style={{ color: '#06b6d4' }}>🟢 {candidateRoleFit?.skills_breakdown?.matched_semantic?.count || 0} semantic matches</li>
                                                        <li style={{ color: '#b45309' }}>🟡 {candidateRoleFit?.skills_breakdown?.partial_emerging?.count || 0} emerging skills</li>
                                                        <li style={{ color: '#e11d48' }}>🔴 {candidateRoleFit?.skills_breakdown?.critical_gaps?.count || 0} critical gaps</li>
                                                    </ul>
                                                </div>
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== SECTION 2: EVIDENCE STRENGTH (SIMPLIFIED) ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">🔍</span>Interview Talking Points</p>
                                            <div style={{ marginTop: '0.35rem', padding: '0.8rem', background: 'linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%)', borderRadius: '8px', border: '1px solid #ddd6fe' }}>
                                                <div style={{ fontSize: '0.9rem', lineHeight: '1.6' }}>
                                                    <p style={{ marginBottom: '0.4rem', color: '#28a745', fontWeight: '600' }}>
                                                        ✅ Discuss in depth: {candidateEvidence?.interview_talking_points?.discuss_in_depth?.slice(0, 3).join(', ') || 'Your core strengths'}
                                                    </p>
                                                    <p style={{ marginBottom: '0.4rem', color: '#856404', fontWeight: '600' }}>
                                                        🟡 Can briefly mention: {candidateEvidence?.interview_talking_points?.can_briefly_mention?.slice(0, 2).join(', ') || 'Related skills'}
                                                    </p>
                                                    <p style={{ color: '#c7254e', fontWeight: '600' }}>
                                                        ❌ Avoid claiming: {candidateEvidence?.interview_talking_points?.avoid_claiming?.slice(0, 2).join(', ') || 'Unproven skills'}
                                                    </p>
                                                </div>
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== SECTION 3: GAP CLOSURE ROADMAP ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">🛣️</span>Gap Closure Learning Roadmap</p>
                                            <div className="evidence-improvement-list">
                                                {Array.isArray(candidateGapRoadmap) && candidateGapRoadmap.length > 0 ? (
                                                    candidateGapRoadmap.slice(0, 4).map((gap, idx) => (
                                                        <article className="evidence-improvement-item" key={`gap-${idx}`} style={{ background: gap.priority === 'CRITICAL' ? 'linear-gradient(135deg, #fff1f5 0%, #ffe4e6 100%)' : 'linear-gradient(135deg, #fdf8f0 0%, #fef3c7 100%)', borderLeft: `4px solid ${gap.priority === 'CRITICAL' ? '#e11d48' : '#f59e0b'}` }}>
                                                            <h5 style={{ marginBottom: '0.4rem' }}>
                                                                {gap.priority === 'CRITICAL' ? '🔴' : '🟡'} {gap.skill}
                                                                <span style={{ marginLeft: '0.5rem', fontSize: '0.85rem', fontWeight: '400', color: '#666' }}>
                                                                    {gap.difficulty}
                                                                </span>
                                                            </h5>
                                                            <p style={{ marginBottom: '0.3rem', fontSize: '0.9rem' }}>
                                                                <strong>Timeline:</strong> {gap.weeks_to_proficiency} weeks ({gap.realistic_timeline})
                                                            </p>
                                                            <p style={{ marginBottom: '0.3rem', fontSize: '0.9rem' }}>
                                                                <strong>Why needed:</strong> {gap.why_needed}
                                                            </p>
                                                            <div style={{ marginTop: '0.4rem', paddingTop: '0.4rem', borderTop: '1px solid #e0e0e0' }}>
                                                                <p style={{ fontSize: '0.85rem', fontWeight: '600', marginBottom: '0.2rem' }}>Learning Path:</p>
                                                                <ul style={{ paddingLeft: '1.2rem', fontSize: '0.85rem', margin: '0.2rem 0' }}>
                                                                    {gap.learning_phases && gap.learning_phases.slice(0, 3).map((phase, pidx) => (
                                                                        <li key={`phase-${pidx}`}>{phase}</li>
                                                                    ))}
                                                                </ul>
                                                            </div>
                                                            <p style={{ marginTop: '0.4rem', fontSize: '0.85rem', color: '#059669', fontWeight: '600' }}>
                                                                Evidence: {gap.evidence_artifact}
                                                            </p>
                                                            <p style={{ marginTop: '0.3rem', fontSize: '0.85rem', color: '#666', fontStyle: 'italic' }}>
                                                                Interview: {gap.interview_signal}
                                                            </p>
                                                            <p style={{ marginTop: '0.3rem', fontSize: '0.85rem' }}>
                                                                <strong>Match boost:</strong> {gap.expected_boost}
                                                            </p>
                                                        </article>
                                                    ))
                                                ) : (
                                                    <p className="insight-subtext">No critical gaps identified. You're well-prepared!</p>
                                                )}
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== SECTION 5: CAREER INSIGHTS ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card">
                                            <p className="doc-label"><span className="evidence-emoji">🎯</span>Career Insights & Growth Path</p>
                                            <div className="evidence-narrative-columns">
                                                <div style={{ background: 'linear-gradient(135deg, #ecf7fc 0%, #cffafe 100%)', border: '1px solid #a5f3fc', borderRadius: '12px', padding: '0.8rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.3rem', color: '#06b6d4' }}>This Role Fit</h5>
                                                    <p style={{ fontSize: '0.9rem', margin: '0.3rem 0' }}>
                                                        <strong>Level:</strong> {candidateCareer?.this_role?.level_match || 'Good Match'}
                                                    </p>
                                                    <p style={{ fontSize: '0.9rem', margin: '0.3rem 0' }}>
                                                        <strong>Day 1:</strong> {candidateCareer?.this_role?.day_one_impact || 'Will need ramp-up'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%)', border: '1px solid #6ee7b7', borderRadius: '12px', padding: '0.8rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.3rem', color: '#059669' }}>Career Path</h5>
                                                    <p style={{ fontSize: '0.9rem', margin: '0.3rem 0' }}>
                                                        <strong>Next Level:</strong> {candidateCareer?.career_path?.next_level_opportunity || 'Senior Engineer'}
                                                    </p>
                                                    <p style={{ fontSize: '0.9rem', margin: '0.3rem 0' }}>
                                                        <strong>Timeline:</strong> {candidateCareer?.career_path?.timeline_to_next_level || '3-4 years'}
                                                    </p>
                                                </div>
                                                <div style={{ background: 'linear-gradient(135deg, #fdf8f0 0%, #fef3c7 100%)', border: '1px solid #fcd34d', borderRadius: '12px', padding: '0.8rem 1rem' }}>
                                                    <h5 style={{ marginBottom: '0.3rem', color: '#b45309' }}>Long-Term Value</h5>
                                                    <p style={{ fontSize: '0.9rem', lineHeight: '1.4' }}>
                                                        {candidateCareer?.long_term_value || 'This role provides valuable skills for future growth'}
                                                    </p>
                                                </div>
                                            </div>
                                        </article>
                                    </section>

                                    {/* ===== RECOMMENDATION ===== */}
                                    <section className="evidence-narrative-grid">
                                        <article className="document-card evidence-narrative-card" style={{ background: '#f0fdf4', border: '2px solid #28a745' }}>
                                            <p className="doc-label"><span className="evidence-emoji">💡</span>Recommended Next Step</p>
                                            <h4 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', color: '#28a745', fontWeight: '700' }}>
                                                {candidateGuidance?.recommended_action || 'Follow your action plan'}
                                            </h4>
                                            <p style={{ fontSize: '0.95rem', lineHeight: '1.6', margin: '0.5rem 0' }}>
                                                {candidateGuidance?.primary_message || 'Work on closing key gaps to strengthen your candidacy'}
                                            </p>
                                        </article>
                                    </section>
                                </>
                            )}

                            {!matchEvidence.length ? (
                                <div className="results-empty">No evidence rows were generated for this run.</div>
                            ) : null}
                </section>
            );
        }

        if (activePage === 'documents') {
            return (
                <section className="documents-panel documents-preview-only fade-in neo-panel">
                    {extractedData ? (
                        <>
                            <section className="documents-text-compare">
                                <article className="document-card text-preview-card">
                                    <div className="text-preview-header" style={{ alignItems: 'flex-start' }}>
                                        <div>
                                            <p className="doc-label">Parsed Job Description</p>
                                            <p className="doc-value">{extractedData.jd_filename || 'Manual Input'}</p>
                                        </div>
                                        <div style={{ textAlign: 'right' }}>
                                            <p className="text-metrics" style={{ fontWeight: '700', fontSize: '0.86rem', color: '#1e293b' }}>{getWordCount(extractedData.job_description_text)} words</p>
                                            <p className="text-metrics" style={{ marginTop: '0.15rem', fontSize: '0.74rem' }}>{jdFile ? formatFileSize(jdFile.size) : jdText.trim() ? 'Manual input' : 'Size N/A'}</p>
                                        </div>
                                    </div>
                                    <div className="parsed-preview-body">
                                        {buildHighlightedPreview(extractedData.job_description_text, jdHighlightEntries)}
                                        <div className="preview-scroll-buffer" aria-hidden="true" />
                                    </div>
                                </article>

                                <article className="document-card text-preview-card">
                                    <div className="text-preview-header" style={{ alignItems: 'flex-start' }}>
                                        <div>
                                            <p className="doc-label">Parsed Resume Content</p>
                                            <p className="doc-value">{extractedData.resume_filename || 'Uploaded File'}</p>
                                        </div>
                                        <div style={{ textAlign: 'right' }}>
                                            <p className="text-metrics" style={{ fontWeight: '700', fontSize: '0.86rem', color: '#1e293b' }}>{getWordCount(extractedData.resume_text)} words</p>
                                            <p className="text-metrics" style={{ marginTop: '0.15rem', fontSize: '0.74rem' }}>{resume ? formatFileSize(resume.size) : 'Size N/A'}</p>
                                        </div>
                                    </div>
                                    <div className="parsed-preview-body">
                                        {buildHighlightedPreview(extractedData.resume_text, resumeHighlightEntries)}
                                        <div className="preview-scroll-buffer" aria-hidden="true" />
                                    </div>
                                </article>
                            </section>
                        </>
                    ) : (
                        <div className="results-empty">
                            Run an assessment to unlock semantic insights, skill-gap summary, and side-by-side parsed content previews.
                        </div>
                    )}
                </section>
            );
        }

        if (activePage === 'multi-resume') {
            return <MultiResumeAnalysis domainOptions={domainOptions} />;
        }

        if (activePage === 'analysis-history') {
            if (!isAdmin) {
                return (
                    <section className="documents-panel fade-in neo-panel">
                        <div className="results-empty">Admin access required to view analysis history.</div>
                    </section>
                );
            }

            if (historyLoading) {
                return (
                    <section className="documents-panel fade-in neo-panel">
                        <div className="results-empty">Loading analysis history...</div>
                    </section>
                );
            }

            if (historyError) {
                return (
                    <section className="documents-panel fade-in neo-panel">
                        <div className="error-message fade-in">{historyError}</div>
                    </section>
                );
            }

            if (!analysisHistory.length) {
                return (
                    <section className="documents-panel fade-in neo-panel">
                        <div className="results-empty">No analysis history found yet.</div>
                    </section>
                );
            }

            return (
                <section className="documents-panel fade-in neo-panel analysis-history-panel">
                    <div className="analysis-history-grid">
                        {analysisHistory.map((item) => {
                            const summary = item?.summary || {};
                            const overallMatch = Number(
                                summary?.overall_match_percentage
                                ?? item?.result_json?.bert_results?.overall_match_percentage
                                ?? item?.result_json?.bert_results?.summary?.overall_alignment_score
                                ?? 0
                            );

                            return (
                                <article className="analysis-history-card" key={item.id}>
                                    <div className="analysis-history-head">
                                        <p className="doc-label">User</p>
                                        <p className="doc-value">{item.user_email || 'unknown_user'}</p>
                                    </div>

                                    {(() => {
                                        const result = item?.result_json || {};
                                        const bertResults = result?.bert_results || {};
                                        const bertSummary = bertResults?.summary || {};
                                        const skillPartition = bertResults?.skill_partition || {};
                                        const aiEnrichmentResult = result?.ai_enrichment || {};
                                        const aiQuality = aiEnrichmentResult?.quality || {};
                                        const hrExec = result?.hr_decision_layer?.executive_recommendation || {};
                                        const candidateGuidanceResult = result?.candidate_decision_layer?.overall_guidance || {};

                                        const normalizeSkills = (arr) => (
                                            Array.isArray(arr)
                                                ? arr
                                                    .map((entry) => {
                                                        if (typeof entry === 'string') return entry;
                                                        if (entry && typeof entry === 'object') {
                                                            return entry.skill || entry.name || entry.term || entry.label || '';
                                                        }
                                                        return '';
                                                    })
                                                    .map((value) => String(value || '').trim())
                                                    .filter(Boolean)
                                                : []
                                        );

                                        const exactSkills = normalizeSkills(skillPartition?.exact_match || []);
                                        const matchedSkills = normalizeSkills(summary?.matched_skills || []);
                                        const missingSkills = normalizeSkills(
                                            summary?.missing_skills
                                            || (Array.isArray(bertResults?.missing_from_resume)
                                                ? bertResults.missing_from_resume.map((entry) => (typeof entry === 'string' ? entry : entry?.skill || ''))
                                                : [])
                                        );

                                        const strongSemantic = Array.isArray(skillPartition?.strong_semantic) ? skillPartition.strong_semantic.length : 0;
                                        const moderateSemantic = Array.isArray(skillPartition?.moderate_semantic) ? skillPartition.moderate_semantic.length : 0;

                                        const exactCount = Number(bertSummary?.exact_match_count ?? exactSkills.length ?? 0);
                                        const semanticCount = Number(bertSummary?.semantic_match_count ?? (strongSemantic + moderateSemantic));
                                        const missingCount = Number(bertSummary?.missing_skills_count ?? missingSkills.length ?? 0);

                                        const topMatchedText = normalizeSkills(exactSkills.length ? exactSkills : matchedSkills).slice(0, 4).join(', ') || 'N/A';
                                        const topMissingText = missingSkills.slice(0, 4).join(', ') || 'N/A';
                                        const aiCoveragePercent = Math.round((Number(aiQuality?.coverage_score || 0)) * 100);

                                        return (
                                            <div className="analysis-mini-grid">
                                                <section className="analysis-mini-section">
                                                    <p className="analysis-mini-title">1. Run Info</p>
                                                    <p><strong>Domain:</strong> {item.domain || 'N/A'}</p>
                                                    <p><strong>JD Source:</strong> {item.jd_source_type || 'N/A'}</p>
                                                    <p><strong>Resume File:</strong> {item.resume_file_name || 'N/A'}</p>
                                                    <p><strong>Created:</strong> {formatIsoTimestamp(item.created_at)}</p>
                                                </section>

                                                <section className="analysis-mini-section">
                                                    <p className="analysis-mini-title">2. Match Metrics</p>
                                                    <p><strong>Overall Match:</strong> {Number.isFinite(overallMatch) ? Math.round(overallMatch) : 0}%</p>
                                                    <p><strong>Exact Matches:</strong> {exactCount}</p>
                                                    <p><strong>Semantic Matches:</strong> {semanticCount}</p>
                                                    <p><strong>Missing Skills:</strong> {missingCount}</p>
                                                </section>

                                                <section className="analysis-mini-section">
                                                    <p className="analysis-mini-title">3. Skills Snapshot</p>
                                                    <p><strong>Top Matched:</strong> {topMatchedText}</p>
                                                    <p><strong>Top Missing:</strong> {topMissingText}</p>
                                                </section>

                                                <section className="analysis-mini-section">
                                                    <p className="analysis-mini-title">4. AI Summary</p>
                                                    <p><strong>Status:</strong> {String(aiEnrichmentResult?.status || 'N/A')}</p>
                                                    <p><strong>Model:</strong> {String(aiEnrichmentResult?.model || 'N/A')}</p>
                                                    <p><strong>Coverage:</strong> {Number.isFinite(aiCoveragePercent) ? aiCoveragePercent : 0}%</p>
                                                    <p><strong>Risk:</strong> {String(aiQuality?.hallucination_risk || 'N/A')}</p>
                                                </section>

                                                <section className="analysis-mini-section">
                                                    <p className="analysis-mini-title">5. Decision Signals</p>
                                                    <p><strong>HR Recommendation:</strong> {String(hrExec?.recommendation || hrExec?.summary || 'N/A')}</p>
                                                    <p><strong>Hiring Stage:</strong> {String(hrExec?.hiring_stage || result?.hr_decision_layer?.hiring_readiness?.stage || 'N/A')}</p>
                                                    <p><strong>Candidate Action:</strong> {String(candidateGuidanceResult?.recommended_action || 'N/A')}</p>
                                                </section>
                                            </div>
                                        );
                                    })()}
                                </article>
                            );
                        })}
                    </div>
                </section>
            );
        }

        if (activePage === 'skill-matching') {
            if (!extractedData) {
                return (
                    <section className="documents-panel fade-in neo-panel">
                        <div className="results-empty">
                            Run an assessment to unlock BERT and Spacy skill matching views.
                        </div>
                    </section>
                );
            }

            return (
                <section className="documents-panel fade-in neo-panel" style={{ padding: '0.5rem' }}>
                    <SkillMatchingModal isEmbedded={true} data={extractedData} />
                </section>
            );
        }

        if (activePage === 'visuals') {
            if (!extractedData) {
                return (
                    <section className="documents-panel fade-in neo-panel">
                        <div className="results-empty">
                            Run an assessment to unlock the dashboard.
                        </div>
                    </section>
                );
            }

            return (
                <section className="documents-panel fade-in neo-panel" style={{ padding: '0.5rem' }}>
                    <VisualizationModal isEmbedded={true} data={extractedData} />
                </section>
            );
        }

        if (activePage === 'context-analysis') {
            return <ContextAnalysisPage data={extractedData} />;
        }

        return (
            <>
                <section className="neo-hero-grid">
                    <div className="neo-hero-card">
                        <p className="neo-kicker">AI Assistant</p>
                        <h3>Build a complete capability snapshot for every candidate profile.</h3>
                        <p>
                            Upload resume and JD inputs, run semantic scoring, and export formal recruiter-grade reports.
                        </p>
                    </div>

                    <div className="neo-stats-grid">
                        <div className="neo-stat-card">
                            <p>Alignment Score</p>
                            <h4>{alignmentScore}%</h4>
                        </div>
                        <div className="neo-stat-card">
                            <p>Exact Matches</p>
                            <h4>{matchedSkills}</h4>
                        </div>
                        <div className="neo-stat-card">
                            <p>Semantic Matches</p>
                            <h4>{semanticSkills}</h4>
                        </div>
                        <div className="neo-stat-card">
                            <p>Missing Skills</p>
                            <h4>{missingSkills}</h4>
                        </div>
                    </div>
                </section>

                <section className="domain-section neo-panel">
                    <div className="section-heading-row">
                        <h3 className="section-title">Domain Configuration</h3>
                    </div>

                    <div className="domain-dropdown">
                        <button
                            className="domain-trigger"
                            onClick={() => setIsDomainOpen(!isDomainOpen)}
                        >
                            <div className="domain-trigger-content">
                                <span className="domain-emoji">{selectedDomain?.icon}</span>
                                <span>{selectedDomain?.label}</span>
                            </div>
                            <ChevronDown
                                size={18}
                                style={{
                                    transform: isDomainOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                                    transition: 'transform 0.2s ease'
                                }}
                            />
                        </button>

                        {isDomainOpen && (
                            <div className="domain-menu fade-in">
                                {domainOptions.map(opt => (
                                    <button
                                        key={opt.id}
                                        className={`domain-option ${domain === opt.id ? 'active' : ''}`}
                                        onClick={() => {
                                            setDomain(opt.id);
                                            setIsDomainOpen(false);
                                        }}
                                    >
                                        <span>{opt.icon}</span>
                                        <span>{opt.label}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </section>

                <section className="workspace-grid neo-panel">
                    <div>
                        <div className="section-heading-row">
                            <h3 className="section-title">Job Description</h3>
                        </div>
                        <div className="setup-card">
                            <JdInput
                                onFileSelect={setJdFile}
                                onTextChange={setJdText}
                                selectedFile={jdFile}
                            />
                        </div>
                    </div>

                    <div>
                        <div className="section-heading-row">
                            <h3 className="section-title">Candidate Resume</h3>
                        </div>
                        <div className="setup-card">
                            <div className="file-placeholder-spacing" />
                            <FileUpload
                                onFileSelect={setResume}
                                selectedFile={resume}
                                accept=".pdf,.docx,.txt"
                                label="Resume"
                            />
                            {resume && (
                                <div className="attached-file-note">
                                    Attached file: {resume.name}
                                </div>
                            )}
                        </div>
                    </div>
                </section>

                <section className="action-section">
                    <button
                        className="btn workspace-run-btn"
                        onClick={handleExtract}
                        disabled={isAnalyzeDisabled}
                    >
                        {loading ? 'Running Analysis...' : 'Run Analysis'}
                    </button>
                </section>

                <section className="pipeline-strip neo-panel">
                    <div className={`pipeline-item ${stageStep >= 1 ? 'complete' : ''}`}>
                        {stageStep >= 1 ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                        <span>Input Capture</span>
                    </div>
                    <div className={`pipeline-item ${loading ? 'active' : ''} ${stageStep >= 2 ? 'complete' : ''}`}>
                        {loading ? <Loader2 size={16} className="spin" /> : stageStep >= 2 ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                        <span>Semantic Processing</span>
                    </div>
                    <div className={`pipeline-item ${stageStep >= 3 ? 'complete' : ''}`}>
                        {stageStep >= 3 ? <CheckCircle2 size={16} /> : <Circle size={16} />}
                        <span>Executive Reporting</span>
                    </div>
                </section>

                {loading && (
                    <div className="loading-instruction-card fade-in" style={{
                        marginTop: '1.5rem',
                        padding: '1.5rem',
                        background: '#f8fafc',
                        border: '1px solid #cbd5e1',
                        borderRadius: '12px',
                        textAlign: 'center',
                        color: '#334155',
                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
                    }}>
                        <h4 style={{ color: '#0f172a', marginBottom: '0.5rem', fontSize: '1.1rem' }}>Processing Your Document...</h4>
                        <p style={{ fontSize: '0.9rem', opacity: 0.85, maxWidth: '600px', margin: '0 auto' }}>
                            We are currently extracting skills, running taxonomy comparisons, and doing deep contextual AI analysis to build your personalized dashboard. This normally takes 10-20 seconds.
                        </p>
                        
                        {loadingTimeExceeded && (
                            <div className="fade-in" style={{ marginTop: '1.2rem', padding: '1rem', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', color: '#b91c1c', maxWidth: '600px', margin: '1.2rem auto 0' }}>
                                <strong style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                                    <AlertCircle size={18} />
                                    Taking longer than expected?
                                </strong>
                                <p style={{ fontSize: '0.85rem', marginTop: '0.4rem', opacity: 0.9 }}>
                                    The AI servers might be experiencing high traffic or a temporary timeout. Please refresh the page and kindly try again.
                                </p>
                            </div>
                        )}
                    </div>
                )}

                {error && (
                    <div className="error-message fade-in">
                        {error}
                    </div>
                )}
            </>
        );
    };

    if (activePage === 'landing') {
        return <LandingPage onStart={() => setActivePage('workspace')} />;
    }

    return (
        <div className="app-container fade-in">
            <div className="app-layout">
                <aside className={`sidebar-glass ${isCompactScreen ? 'mobile-drawer' : ''} ${isSidebarOpen ? 'open' : ''}`}>
                    <div className="sidebar-brand-block">
                        <button
                            className="brand-orb"
                            aria-label="Resume Analyzer Home"
                            onClick={() => {
                                setActivePage('landing');
                                if (isCompactScreen) setIsSidebarOpen(false);
                            }}
                        >
                            ✶
                        </button>
                        {isCompactScreen && (
                            <button
                                className="mobile-drawer-close"
                                onClick={() => setIsSidebarOpen(false)}
                                aria-label="Close sidebar"
                            >
                                <X size={16} />
                            </button>
                        )}
                    </div>

                    <nav className="sidebar-nav">
                        {navItems.map(item => {
                            const Icon = item.icon;
                            return (
                                <button
                                    key={item.id}
                                    className={`sidebar-nav-item ${activePage === item.id ? 'active' : ''}`}
                                    onClick={() => {
                                        setActivePage(item.id);
                                        if (isCompactScreen) setIsSidebarOpen(false);
                                    }}
                                    title={item.label}
                                >
                                    <Icon size={18} />
                                    <span className="sidebar-nav-label">{item.label}</span>
                                </button>
                            );
                        })}
                    </nav>

                    <div className="sidebar-action-stack">
                        {extractedData && (
                            <button className="sidebar-action-btn primary" onClick={handleExportPdf} disabled={isGeneratingPDF}>
                                <FileDown size={16} />
                                <span>{isGeneratingPDF ? 'Exporting...' : 'Export PDF'}</span>
                            </button>
                        )}
                        <button
                            className="sidebar-action-btn secondary"
                            onClick={() => {
                                setActivePage('multi-resume');
                                if (isCompactScreen) setIsSidebarOpen(false);
                            }}
                        >
                            <Files size={16} />
                            <span>Multi Resume</span>
                        </button>
                    </div>

                    <div className="sidebar-mini-card">
                        <p className="doc-label">Current Domain</p>
                        <p className="doc-value">{selectedDomain?.label}</p>
                    </div>
                </aside>

                {isCompactScreen && isSidebarOpen && (
                    <button
                        className="mobile-sidebar-backdrop show"
                        aria-label="Close sidebar backdrop"
                        onClick={() => setIsSidebarOpen(false)}
                    />
                )}

                <main className={`glass-card professional-shell page-panel ${!isCompactScreen && activePage === 'workspace' ? 'workspace-no-scroll' : ''} ${!isCompactScreen && activePage === 'documents' ? 'documents-no-scroll' : ''} ${!isCompactScreen && activePage === 'evidence' ? 'evidence-no-scroll' : ''}`}>
                    <header className="professional-header">
                        {isCompactScreen && (
                            <button
                                className="mobile-sidebar-toggle"
                                onClick={() => setIsSidebarOpen(true)}
                                aria-label="Open sidebar"
                            >
                                <Menu size={18} />
                                <span>Menu</span>
                            </button>
                        )}
                        <div className="header-info-group">
                            <h1 className={`title ${activePage === 'documents' ? 'documents-title' : ''}`}>
                                {activePage === 'workspace' && 'Assessment Workspace'}
                                {activePage === 'multi-resume' && 'Multi-Resume Analysis'}
                                {activePage === 'analysis-history' && 'Analysis History'}
                                {activePage === 'documents' && 'Document Overview'}
                                {activePage === 'evidence' && 'Evidence Layer'}
                                {activePage === 'skill-matching' && 'Skill Matching'}
                                {activePage === 'visuals' && 'Visual Analytics'}
                                {activePage === 'context-analysis' && 'Context Analysis Evidence'}
                            </h1>
                        </div>

                        <div className={`header-right-actions ${activePage === 'documents' ? 'documents-actions-inline' : ''}`}>
                            {activePage !== 'multi-resume' && activePage !== 'analysis-history' && (
                                <button className="title-cta-btn" onClick={handleStartNewRun}>Start New Run</button>
                            )}
                            {activePage === 'documents' && extractedData && (
                                <div className="documents-highlight-toolbar documents-header-tools">
                                    <button
                                        className={`highlight-toggle-btn ${isHighlightEnabled ? 'active' : ''}`}
                                        onClick={() => setIsHighlightEnabled((prev) => !prev)}
                                    >
                                        {isHighlightEnabled ? 'Remove Highlight' : 'Highlighter'}
                                    </button>

                                    <div className="highlight-legend">
                                        <span className="legend-pill match">Match</span>
                                        <span className="legend-pill partial">Partial Match</span>
                                        <span className="legend-pill missing">Missing</span>
                                        <span className="legend-pill additional">Additional Skills</span>
                                    </div>
                                </div>
                            )}
                        </div>
                    </header>

                    <div className="page-content-shell">
                        {renderMainContent()}
                    </div>
                </main>
            </div>

            <PdfProgressModal visible={showPdfProgress} progress={pdfProgress} label={pdfProgressLabel} />
            <ContextChatbot extractedData={extractedData} />
        </div>
    );
}

function App() {
    return <AppContent />;
}

export default App;
