import React from 'react';
import ReactDOM from 'react-dom';
import { X, BarChart3, PieChart as PieChartIcon, Target, AlertTriangle, Layers, Activity } from 'lucide-react';
import {
    PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
    BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Radar, RadarChart, PolarGrid, PolarAngleAxis
} from 'recharts';

const VisualizationModal = ({ isOpen, onClose, isClosing, data, isEmbedded = false }) => {
    if (!isEmbedded && !isOpen) return null;

    const skillsMapRef = React.useRef(null);
    const visualScrollRef = React.useRef(null);
    const [skillsMapVisible, setSkillsMapVisible] = React.useState(false);
    const [activeViz, setActiveViz] = React.useState('progression');

    const vizTabs = [
        { id: 'progression', label: 'Skill Match Progression' },
        { id: 'heatmap', label: 'Category Risk Heatmap' },
        { id: 'semantic', label: 'Semantic Convergence' },
        { id: 'domain', label: 'Domain Skill Categories' },
    ];

    const bertResults = data.bert_results || {};
    const summary = bertResults.summary || { overall_alignment_score: 0, exact_match_count: 0, semantic_match_count: 0, missing_skills_count: 0 };
    const partition = bertResults.skill_partition || { exact_match: [], strong_semantic: [], moderate_semantic: [], irrelevant: [] };
    const missingFromResume = bertResults.missing_from_resume || [];
    const jdClusters = bertResults.jd_skill_clusters || {};
    const jdCategorizedSkills = data.jd_skills?.categorized_skills || {};
    const resumeCategorizedSkills = data.resume_skills?.categorized_skills || {};

    // Default Colors
    const COLORS = {
        success: '#10b981',
        warning: '#f59e0b',
        danger: '#ef4444',
        info: '#3b82f6',
        neutral: '#cbd5e1',
        purple: '#8b5cf6'
    };

    // 1. Gauge Data
    const score = summary.overall_alignment_score;
    const gaugeColor = score >= 75 ? COLORS.success : score >= 50 ? COLORS.warning : COLORS.danger;
    const gaugeData = [
        { name: 'Score', value: score, fill: gaugeColor },
        { name: 'Remaining', value: Math.max(100 - score, 0), fill: COLORS.neutral }
    ];

    // 2. Match Distribution Data
    const matchData = [
        { name: 'Exact Matches', value: summary.exact_match_count, fill: COLORS.success },
        { name: 'Semantic Matches', value: summary.semantic_match_count, fill: COLORS.info },
        { name: 'Missing Skills', value: summary.missing_skills_count, fill: COLORS.danger }
    ].filter(item => item.value > 0);

    // 3. Category Comparison Data (Grouped Bar)
    const resumeClusters = bertResults.resume_skill_clusters || {};
    const allCategories = Array.from(new Set([...Object.keys(jdClusters), ...Object.keys(resumeClusters)]));
    const categoryData = allCategories.map(cat => ({
        category: cat,
        jd: jdClusters[cat] ? jdClusters[cat].length : 0,
        resume: resumeClusters[cat] ? resumeClusters[cat].length : 0
    })).sort((a, b) => b.jd - a.jd).slice(0, 8); // Top 8 categories for sanity

    const matchedJdSkillSet = new Set([
        ...(partition.exact_match || []).map((value) => String(value || '').toLowerCase()),
        ...(partition.strong_semantic || []).map((value) => String(value.similar_to || '').toLowerCase()),
        ...(partition.moderate_semantic || []).map((value) => String(value.similar_to || '').toLowerCase()),
    ]);

    const exactMatchSet = new Set((partition.exact_match || []).map((value) => String(value || '').toLowerCase()));
    const strongMatchSet = new Set((partition.strong_semantic || []).map((value) => String(value.similar_to || '').toLowerCase()));
    const moderateMatchSet = new Set((partition.moderate_semantic || []).map((value) => String(value.similar_to || '').toLowerCase()));
    const missingSkillSet = new Set((missingFromResume || []).map((item) => String(item.skill || '').toLowerCase()));

    const categoryHeatmapRows = Object.keys(jdClusters).map((category) => {
        const requiredSkills = jdClusters[category] || [];
        const requiredCount = requiredSkills.length;
        const coveredCount = requiredSkills.filter((skill) => matchedJdSkillSet.has(String(skill || '').toLowerCase())).length;
        const missingItems = missingFromResume.filter((item) => (item.categories || []).includes(category));
        const missingCount = missingItems.length;
        const weightedRisk = Math.round(missingItems.reduce((acc, item) => acc + Number(item.weight || 1), 0) * 10) / 10;
        const coveragePct = requiredCount > 0 ? Math.round((coveredCount / requiredCount) * 100) : 0;
        return {
            category,
            requiredCount,
            coveredCount,
            missingCount,
            weightedRisk,
            coveragePct,
        };
    }).sort((a, b) => b.weightedRisk - a.weightedRisk);

    // Elegant Color Gradient Functions for Professional Heatmap
    const getColorGradient = (value, type) => {
        // value is 0-100 (or 0-max normalized to 0-100)
        // type: 'coverage' (teal), 'missing' (coral), 'risk' (plum)
        const norm = Math.max(0, Math.min(1, value / 100));
        
        if (type === 'coverage') {
            // Coverage: Cool gradient from light teal to deep teal
            // Light teal (#d1fae5) → Vibrant teal (#14b8a6) → Deep teal (#0d9488)
            const colors = [
                { pos: 0.0, r: 209, g: 250, b: 229 },  // Light mint
                { pos: 0.3, r: 45, g: 212, b: 191 },   // Vibrant teal
                { pos: 0.6, r: 20, g: 184, b: 166 },   // Rich teal
                { pos: 1.0, r: 13, g: 148, b: 136 }    // Deep teal
            ];
            const segment = colors.find((c, i) => norm <= (colors[i + 1]?.pos || 1));
            const nextSegment = colors.find((c, i) => norm > c.pos && (i === colors.length - 1 || norm <= colors[i + 1]?.pos));
            if (!nextSegment) return `rgb(${colors[colors.length - 1].r}, ${colors[colors.length - 1].g}, ${colors[colors.length - 1].b})`;
            return `rgb(${Math.round(segment.r + (nextSegment.r - segment.r) * norm)}, ${Math.round(segment.g + (nextSegment.g - segment.g) * norm)}, ${Math.round(segment.b + (nextSegment.b - segment.b) * norm)})`;
        } else if (type === 'missing') {
            // Missing: Coral to warm gradient (light amber to deep orange)
            // Light cream (#fef3c7) → Soft amber (#fcd34d) → Deep orange (#d97706)
            const colors = [
                { pos: 0.0, r: 254, g: 243, b: 199 },  // Cream
                { pos: 0.3, r: 252, g: 211, b: 77 },   // Soft amber
                { pos: 0.6, r: 245, g: 158, b: 11 },   // Rich amber
                { pos: 1.0, r: 217, g: 119, b: 6 }     // Deep orange
            ];
            const idx = Math.floor(norm * (colors.length - 1));
            const segment = colors[idx];
            const nextSeg = colors[Math.min(idx + 1, colors.length - 1)];
            const localNorm = norm * (colors.length - 1) - idx;
            return `rgb(${Math.round(segment.r + (nextSeg.r - segment.r) * localNorm)}, ${Math.round(segment.g + (nextSeg.g - segment.g) * localNorm)}, ${Math.round(segment.b + (nextSeg.b - segment.b) * localNorm)})`;
        } else {
            // Risk: Elegant rose to plum gradient
            // Light rose (#fce7f3) → Soft coral (#f472b6) → Deep plum (#be185d)
            const colors = [
                { pos: 0.0, r: 252, g: 231, b: 243 },  // Light rose
                { pos: 0.3, r: 244, g: 114, b: 182 },  // Soft coral
                { pos: 0.6, r: 219, g: 39, b: 119 },   // Rich rose
                { pos: 1.0, r: 190, g: 24, b: 93 }     // Deep plum
            ];
            const idx = Math.floor(norm * (colors.length - 1));
            const segment = colors[idx];
            const nextSeg = colors[Math.min(idx + 1, colors.length - 1)];
            const localNorm = norm * (colors.length - 1) - idx;
            return `rgb(${Math.round(segment.r + (nextSeg.r - segment.r) * localNorm)}, ${Math.round(segment.g + (nextSeg.g - segment.g) * localNorm)}, ${Math.round(segment.b + (nextSeg.b - segment.b) * localNorm)})`;
        }
    };

    // Smart text color based on background brightness
    const getTextColorForBackground = (bgColor, lightText = '#f8fafc', darkText = '#1f2937') => {
        const rgbMatch = bgColor.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
        if (!rgbMatch) return lightText;
        const [, r, g, b] = rgbMatch;
        const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
        return luminance > 0.5 ? darkText : lightText;
    };

    const normalizeSkill = (skill) => {
        if (typeof skill === 'object' && skill !== null) {
            return String(skill.skill || '').trim();
        }
        return String(skill || '').trim();
    };

    const skillBoxCategories = Array.from(new Set([
        ...Object.keys(jdClusters || {}),
        ...Object.keys(jdCategorizedSkills || {}),
        ...Object.keys(resumeCategorizedSkills || {}),
    ]));

    const categorySkillBoxData = skillBoxCategories.map((category) => {
        const requiredSource = (jdClusters?.[category] && jdClusters[category].length > 0)
            ? jdClusters[category]
            : ((jdCategorizedSkills?.[category] && jdCategorizedSkills[category].length > 0)
                ? jdCategorizedSkills[category]
                : (resumeCategorizedSkills?.[category] || []));

        const resumeSource = (resumeCategorizedSkills?.[category] && resumeCategorizedSkills[category].length > 0)
            ? resumeCategorizedSkills[category]
            : (resumeClusters?.[category] || []);

        const requiredSkills = Array.from(new Set((requiredSource || []).map(normalizeSkill).filter(Boolean)));
        const resumeCategorySet = new Set((resumeSource || []).map(normalizeSkill).filter(Boolean).map((value) => value.toLowerCase()));

        const skillItems = requiredSkills.map((skill) => {
            const normalized = skill.toLowerCase();
            let status = 'missing';

            if (exactMatchSet.has(normalized)) {
                status = 'exact';
            } else if (strongMatchSet.has(normalized)) {
                status = 'strong';
            } else if (moderateMatchSet.has(normalized)) {
                status = 'moderate';
            } else if (resumeCategorySet.has(normalized)) {
                status = 'strong';
            } else if (!missingSkillSet.has(normalized) && matchedJdSkillSet.has(normalized)) {
                status = 'strong';
            }

            return { skill, status };
        });

        const presentCount = skillItems.filter((item) => item.status !== 'missing').length;
        const coverage = requiredSkills.length > 0 ? Math.round((presentCount / requiredSkills.length) * 100) : 0;

        return {
            category,
            total: requiredSkills.length,
            present: presentCount,
            coverage,
            skillItems,
        };
    }).filter((item) => item.total > 0).sort((a, b) => b.total - a.total);

    const syntheticFallbackTiles = [
        {
            category: 'Exact Matches',
            skillItems: (partition.exact_match || []).map((skill) => ({ skill: String(skill || ''), status: 'exact' })),
        },
        {
            category: 'Strong Semantic',
            skillItems: (partition.strong_semantic || []).map((item) => ({ skill: String(item?.similar_to || item?.skill || ''), status: 'strong' })),
        },
        {
            category: 'Moderate Semantic',
            skillItems: (partition.moderate_semantic || []).map((item) => ({ skill: String(item?.similar_to || item?.skill || ''), status: 'moderate' })),
        },
        {
            category: 'Missing Skills',
            skillItems: (missingFromResume || []).map((item) => ({ skill: String(item?.skill || ''), status: 'missing' })),
        },
    ].map((tile) => {
        const cleanedItems = tile.skillItems
            .map((entry) => ({ skill: String(entry.skill || '').trim(), status: entry.status }))
            .filter((entry) => entry.skill.length > 0);
        const total = cleanedItems.length;
        const present = cleanedItems.filter((entry) => entry.status !== 'missing').length;
        const coverage = total > 0 ? Math.round((present / total) * 100) : 0;
        return {
            category: tile.category,
            total,
            present,
            coverage,
            skillItems: cleanedItems,
        };
    }).filter((tile) => tile.total > 0);

    const treemapTiles = (categorySkillBoxData.length > 0 ? categorySkillBoxData : syntheticFallbackTiles)
        .sort((a, b) => b.total - a.total);

    const maxCategoryTileSize = Math.max(1, ...treemapTiles.map((item) => item.total || 0));
    const CATEGORY_SWATCHES = ['#1d4ed8', '#2563eb', '#3b82f6', '#0ea5e9', '#06b6d4', '#10b981', '#84cc16', '#f59e0b', '#f97316', '#ef4444'];

    React.useEffect(() => {
        if (!isOpen) {
            setSkillsMapVisible(false);
            return undefined;
        }

        const target = skillsMapRef.current;
        const scrollRoot = visualScrollRef.current || null;
        if (!target || typeof IntersectionObserver === 'undefined') {
            setSkillsMapVisible(true);
            return undefined;
        }

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setSkillsMapVisible(true);
                    }
                });
            },
            { threshold: 0.15, root: scrollRoot }
        );

        observer.observe(target);
        return () => observer.disconnect();
    }, [isOpen]);

    const funnelData = [
        { stage: 'Total Required', value: summary.total_jd_skills, fill: '#64748b', desc: 'Skills in Job Description' },
        { stage: 'Exact Matches', value: summary.exact_match_count, fill: '#10b981', desc: 'Complete matches found' },
        { stage: 'Semantic Matches', value: summary.semantic_match_count, fill: '#3b82f6', desc: 'Skills semantically related' },
        { stage: 'Coverage Total', value: summary.exact_match_count + summary.semantic_match_count, fill: '#8b5cf6', desc: 'All matches combined' },
    ];

    // 5. Radar Chart (Profile) - Dual Layer with JD and Resume
    const radarData = Object.keys(resumeClusters).map(cat => ({
        subject: cat,
        A: resumeClusters[cat].length,
        B: jdClusters[cat] ? jdClusters[cat].length : 0,
        fullMark: Math.max(10, Math.max(resumeClusters[cat].length, (jdClusters[cat] ? jdClusters[cat].length : 0)) + 2)
    }));

    // 6. Match Confidence Table Data
    const exactMatches = (partition.exact_match || []).map(s => ({ skill: s, type: 'Exact Match', score: 1.0, color: COLORS.success }));
    const strongSemantics = (partition.strong_semantic || []).map(s => ({ skill: s.skill, type: 'Strong Semantic', score: s.score, color: COLORS.info }));
    const moderateSemantics = (partition.moderate_semantic || []).map(s => ({ skill: s.skill, type: 'Moderate Semantic', score: s.score, color: COLORS.warning }));
    const matchTableData = [...exactMatches, ...strongSemantics, ...moderateSemantics].sort((a, b) => b.score - a.score);

    // 8. Semantic Confidence Distribution (Categorized by Backend Match Type)
    const exactCount = (partition.exact_match || []).length;
    const strongCount = (partition.strong_semantic || []).length;
    const moderateCount = (partition.moderate_semantic || []).length;
    const missingCount = (missingFromResume || []).length;

    const buckets = [
        { range: 'Exact Matches', count: exactCount, fill: '#10b981' },
        { range: 'Strong Semantic', count: strongCount, fill: '#3b82f6' },
        { range: 'Moderate Semantic', count: moderateCount, fill: '#f59e0b' },
        { range: 'Missing Skills', count: missingCount, fill: '#ef4444' }
    ];

    const CustomTooltip = ({ active, payload, label }) => {
        if (active && payload && payload.length) {
            return (
                <div style={{ background: '#1e293b', color: 'white', padding: '12px 16px', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)', border: '1px solid #334155' }}>
                    {label && <p style={{ margin: '0 0 8px 0', fontWeight: 'bold', fontSize: '1.05rem', color: '#94a3b8' }}>{label}</p>}
                    {payload.map((entry, index) => (
                        <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '4px 0' }}>
                            <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: entry.color || entry.fill }}></div>
                            <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{entry.name}:</span>
                            <span style={{ fontWeight: 800, fontSize: '1rem', color: entry.color || entry.fill }}>{entry.value}</span>
                        </div>
                    ))}
                </div>
            );
        }
        return null;
    };

    const panelContent = (
            <div
                className={isEmbedded ? '' : `modal-content modal-content-full ${isClosing ? 'slide-down' : ''}`}
                style={{
                    background: 'linear-gradient(180deg, #0f172a 0%, #020617 100%)',
                    maxWidth: isEmbedded ? '100%' : '1400px',
                    margin: isEmbedded ? '0' : '2rem auto',
                    borderRadius: isEmbedded ? '16px' : undefined,
                    border: isEmbedded ? '1px solid #243041' : undefined,
                    overflow: isEmbedded ? 'hidden' : undefined,
                    position: isEmbedded ? 'relative' : undefined,
                    top: isEmbedded ? 'auto' : undefined,
                    left: isEmbedded ? 'auto' : undefined,
                    width: isEmbedded ? '100%' : undefined,
                    maxHeight: isEmbedded ? 'none' : undefined,
                }}
            >

                {!isEmbedded && (
                    <div className="modal-header" style={{
                        padding: '1.5rem 3rem',
                        background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
                        color: 'white',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        position: 'sticky',
                        top: 0,
                        zIndex: 10
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                            <div style={{ background: 'rgba(255,255,255,0.1)', padding: '0.75rem', borderRadius: '12px' }}>
                                <BarChart3 size={32} color="#38bdf8" />
                            </div>
                            <div>
                                <h2 style={{ margin: 0, fontSize: '1.5rem', fontWeight: '800' }}>Visual Analytics Dashboard</h2>
                                <p style={{ margin: '4px 0 0', opacity: 0.8, fontSize: '0.9rem' }}>Comprehensive breakdown of candidate alignment</p>
                            </div>
                        </div>

                        <button className="modal-close-btn" onClick={onClose} style={{ background: 'rgba(255,255,255,0.1)', color: 'white', border: 'none', cursor: 'pointer' }}>
                            <X size={24} />
                        </button>
                    </div>
                )}

                {/* Dashboard Grid */}
                <div ref={visualScrollRef} className="visual-analytics-scroll" style={{ padding: '1.25rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', flex: 1, background: 'transparent' }}>

                    {/* Section 1: Executive Overview (Moved to top) */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.25rem' }}>

                        {/* 1. Alignment Gauge */}
                        <div className="content-card" style={{ background: '#1e293b', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '1.4rem', borderTop: `4px solid ${gaugeColor}` }}>
                            <h3 style={{ margin: '0 0 0.7rem 0', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontSize: '1.05rem' }}>
                                <Target size={18} color={gaugeColor} />
                                Overall Alignment Score
                            </h3>
                            <div style={{ height: 150, width: '100%', position: 'relative', marginTop: '0.55rem' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie data={gaugeData} cx="50%" cy="100%" startAngle={180} endAngle={0} innerRadius={100} outerRadius={140} dataKey="value" stroke="none" />
                                    </PieChart>
                                </ResponsiveContainer>
                                <div style={{ position: 'absolute', bottom: '8px', left: '50%', transform: 'translateX(-50%)', textAlign: 'center' }}>
                                    <span style={{ fontSize: '2.6rem', fontWeight: '900', color: gaugeColor, textShadow: '0 2px 10px rgba(0,0,0,0.5)' }}>{score}%</span>
                                </div>
                            </div>
                        </div>

                        {/* 2. Match Distribution */}
                        <div className="content-card" style={{ background: '#1e293b', padding: '1.4rem', borderTop: `4px solid ${COLORS.purple}` }}>
                            <h3 style={{ margin: '0 0 0.7rem 0', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontSize: '1.05rem' }}>
                                <PieChartIcon size={18} color={COLORS.purple} />
                                Match Distribution
                            </h3>
                            <div style={{ height: 230, width: '100%', display: 'flex', justifyContent: 'center' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                        <Pie
                                            data={matchData}
                                            cx="50%" cy="50%"
                                            innerRadius={50} outerRadius={80}
                                            paddingAngle={5}
                                            dataKey="value"
                                            stroke="none"
                                            label={({ cx, cy, midAngle, innerRadius, outerRadius, value, name, percent }) => {
                                                const RADIAN = Math.PI / 180;
                                                const radius = outerRadius + 20;
                                                const x = cx + radius * Math.cos(-midAngle * RADIAN);
                                                const y = cy + radius * Math.sin(-midAngle * RADIAN);
                                                return (
                                                    <text x={x} y={y} fill="#cbd5e1" textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize="13" fontWeight="600">
                                                        {name} {(percent * 100).toFixed(0)}%
                                                    </text>
                                                );
                                            }}
                                        />
                                        <Tooltip content={<CustomTooltip />} />
                                    </PieChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                    </div>

                    {/* Section 2: Deep Category Analysis */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>

                        {/* 3. Category Comparison Bar Chart */}
                        <div className="content-card" style={{ background: '#1e293b', padding: '1.4rem', borderTop: `4px solid ${COLORS.info}` }}>
                            <h3 style={{ margin: '0 0 0.9rem 0', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontSize: '1.05rem' }}>
                                <Layers size={18} color={COLORS.info} />
                                Skill Category bar chart (JD vs Resume)
                            </h3>
                            <div style={{ height: 340, width: '100%' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={categoryData} margin={{ top: 10, right: 16, left: 0, bottom: 60 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
                                        <XAxis dataKey="category" angle={-40} textAnchor="end" height={78} interval={0} tick={{ fontSize: 11, fill: 'white', fontWeight: 600 }} dx={-3} dy={8} />
                                        <YAxis tick={{ fontSize: 11, fill: 'white', fontWeight: 600 }} allowDecimals={false} />
                                        <Tooltip cursor={{ fill: 'rgba(0,0,0,0.03)' }} content={<CustomTooltip />} />
                                        <Legend verticalAlign="top" height={36} wrapperStyle={{ paddingBottom: '20px' }} />
                                        <Bar dataKey="jd" name="Job Requirement" fill={COLORS.success} radius={[4, 4, 0, 0]} barSize={32} />
                                        <Bar dataKey="resume" name="Resume Possesses" fill={COLORS.info} radius={[4, 4, 0, 0]} barSize={32} />
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* 5. Resume Profile Radar */}
                        <div className="content-card" style={{ background: '#1e293b', padding: '1.4rem', display: 'flex', flexDirection: 'column', borderTop: `4px solid ${COLORS.success}` }}>
                            <h3 style={{ margin: '0 0 0 0', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontSize: '1.05rem' }}>
                                <Activity size={18} color={COLORS.success} />
                                Skill Overlapping Radar chart
                            </h3>
                            <div style={{ marginTop: '0.8rem', minHeight: 320, width: '100%' }}>
                                {radarData.length >= 3 ? (
                                    <ResponsiveContainer width="100%" height={320}>
                                        <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                                            <PolarGrid gridType="circle" stroke="#334155" />
                                            <PolarAngleAxis dataKey="subject" tick={{ fill: 'white', fontSize: 13, fontWeight: 600 }} />
                                            <Radar name="Resume Expertise" dataKey="A" stroke={COLORS.success} strokeWidth={2.5} fill={COLORS.success} fillOpacity={0.35} />
                                            <Radar name="Job Requirements" dataKey="B" stroke={COLORS.info} strokeWidth={2.5} fill={COLORS.info} fillOpacity={0.25} />
                                            <Legend verticalAlign="top" height={36} wrapperStyle={{ paddingBottom: '10px' }} />
                                            <Tooltip content={<CustomTooltip />} />
                                        </RadarChart>
                                    </ResponsiveContainer>
                                ) : (
                                    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', textAlign: 'center', padding: '2rem' }}>
                                        Not enough distinct categories mapped for radar visualization (Need ≥ 3).
                                    </div>
                                )}
                            </div>
                        </div>

                    </div>

                    <div className="content-card" style={{ background: '#1e293b', borderTop: '4px solid #4f46e5', padding: '0.75rem 1rem' }}>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                            {vizTabs.map((tab) => (
                                <button
                                    key={tab.id}
                                    onClick={() => setActiveViz(tab.id)}
                                    style={{
                                        border: activeViz === tab.id ? '1px solid #6366f1' : '1px solid #334155',
                                        background: activeViz === tab.id ? '#4f46e5' : '#0f172a',
                                        color: activeViz === tab.id ? '#ffffff' : '#cbd5e1',
                                        borderRadius: '999px',
                                        padding: '0.36rem 0.75rem',
                                        fontSize: '0.74rem',
                                        fontWeight: 700,
                                        cursor: 'pointer'
                                    }}
                                >
                                    {tab.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Phase 1: Skill Match Breakdown */}
                    {activeViz === 'progression' && (
                    <div className="content-card" style={{ background: '#1e293b', padding: '1.2rem', borderTop: `4px solid ${COLORS.info}` }}>
                        <h3 style={{ margin: '0 0 0.7rem', display: 'flex', alignItems: 'center', gap: '8px', color: 'white', fontSize: '1rem', fontWeight: 900 }}>
                            <Target size={18} color={COLORS.info} />
                            Skill Match Progression
                        </h3>
                        <p style={{ margin: '0 0 1.5rem 0', color: '#94a3b8', fontSize: '0.9rem' }}>Visual breakdown of how candidate skills align with job requirements</p>
                        <div style={{ height: 250, width: '100%' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={funnelData} margin={{ top: 15, right: 30, left: 0, bottom: 40 }}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
                                    <XAxis dataKey="stage" tick={{ fill: '#f8fafc', fontSize: 13, fontWeight: 700 }} axisLine={false} tickLine={false} angle={-15} textAnchor="end" height={80} />
                                    <YAxis allowDecimals={false} tick={{ fill: '#e2e8f0', fontSize: 13, fontWeight: 600 }} axisLine={false} tickLine={false} />
                                    <Tooltip 
                                        cursor={false}
                                        content={({ active, payload }) => {
                                            if (active && payload && payload.length) {
                                                return (
                                                    <div style={{ background: '#1e293b', color: 'white', padding: '12px 16px', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)', border: '1px solid #334155' }}>
                                                        <p style={{ margin: '0 0 4px 0', fontWeight: 'bold', fontSize: '0.95rem' }}>{payload[0].payload.stage}</p>
                                                        <p style={{ margin: '0 0 4px 0', color: '#94a3b8', fontSize: '0.85rem' }}>{payload[0].payload.desc}</p>
                                                        <p style={{ margin: 0, fontWeight: 800, fontSize: '1.1rem', color: payload[0].fill }}>{payload[0].value} skills</p>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                    <Bar dataKey="value" name="Skills Count" radius={[10, 10, 0, 0]} barSize={60}>
                                        {funnelData.map((entry, idx) => (
                                            <Cell key={`fn-${entry.stage}-${idx}`} fill={entry.fill} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                    )}

                    {/* Phase 1: Category Risk Heatmap - Professional Gradient Design */}
                    {activeViz === 'heatmap' && (
                    <div className="content-card" style={{ background: 'linear-gradient(135deg, #1e293b 0%, #1a1f35 100%)', padding: '1.2rem', borderTop: `4px solid ${COLORS.warning}`, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
                        <h3 style={{ margin: '0 0 0.8rem', display: 'flex', alignItems: 'center', gap: '8px', color: '#f1f5f9', fontSize: '1rem', letterSpacing: '0.2px' }}>
                            <Layers size={18} color={COLORS.warning} />
                            Category Risk Heatmap
                        </h3>
                        <div style={{ border: '1px solid #475569', borderRadius: '14px', overflow: 'hidden', boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.2)' }}>
                            {/* Header Row */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 2fr) repeat(3, minmax(120px, 1fr))', background: 'linear-gradient(135deg, #0f1729 0%, #1a1f35 100%)', borderBottom: '2px solid #475569' }}>
                                <div style={{ padding: '0.65rem 0.9rem', color: '#cbd5e1', fontSize: '0.72rem', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px' }}>Category</div>
                                <div style={{ padding: '0.65rem 0.8rem', color: '#14b8a6', fontSize: '0.72rem', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px' }}>Coverage</div>
                                <div style={{ padding: '0.65rem 0.8rem', color: '#f59e0b', fontSize: '0.72rem', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px' }}>Missing</div>
                                <div style={{ padding: '0.65rem 0.8rem', color: '#ec4899', fontSize: '0.72rem', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '1px' }}>Risk</div>
                            </div>

                            {/* Data Rows */}
                            {categoryHeatmapRows.map((row, idx) => {
                                // Normalize values to 0-100 scale
                                const coverageValue = Math.max(0, Math.min(100, row.coveragePct || 0));
                                const maxMissing = Math.max(1, ...categoryHeatmapRows.map(r => r.missingCount || 0));
                                const maxRisk = Math.max(1, ...categoryHeatmapRows.map(r => r.weightedRisk || 0));
                                const missingNorm = ((row.missingCount || 0) / maxMissing) * 100;
                                const riskNorm = ((row.weightedRisk || 0) / maxRisk) * 100;

                                const coverageColor = getColorGradient(coverageValue, 'coverage');
                                const missingColor = getColorGradient(missingNorm, 'missing');
                                const riskColor = getColorGradient(riskNorm, 'risk');

                                const coverageTextColor = getTextColorForBackground(coverageColor);
                                const missingTextColor = getTextColorForBackground(missingColor);
                                const riskTextColor = getTextColorForBackground(riskColor);

                                return (
                                    <div key={`${row.category}-${idx}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(180px, 2fr) repeat(3, minmax(120px, 1fr))', borderBottom: idx === categoryHeatmapRows.length - 1 ? 'none' : '1px solid #334155', background: '#0a0f1a', transition: 'background 0.15s ease' }}>
                                        <div style={{ padding: '0.7rem 0.9rem', color: '#e2e8f0', fontSize: '0.87rem', fontWeight: 600, display: 'flex', alignItems: 'center' }}>{row.category}</div>
                                        <div 
                                            style={{ 
                                                padding: '0.7rem 0.8rem', 
                                                background: coverageColor,
                                                color: coverageTextColor,
                                                fontWeight: 800, 
                                                fontSize: '0.83rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                borderRadius: '6px',
                                                margin: '4px',
                                                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                                                textShadow: '0 1px 1px rgba(0,0,0,0.1)'
                                            }}>
                                            {row.coveragePct}%
                                        </div>
                                        <div 
                                            style={{ 
                                                padding: '0.7rem 0.8rem', 
                                                background: missingColor,
                                                color: missingTextColor,
                                                fontWeight: 800, 
                                                fontSize: '0.83rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                borderRadius: '6px',
                                                margin: '4px',
                                                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                                                textShadow: '0 1px 1px rgba(0,0,0,0.1)'
                                            }}>
                                            {row.missingCount}
                                        </div>
                                        <div 
                                            style={{ 
                                                padding: '0.7rem 0.8rem', 
                                                background: riskColor,
                                                color: riskTextColor,
                                                fontWeight: 800, 
                                                fontSize: '0.83rem',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                borderRadius: '6px',
                                                margin: '4px',
                                                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                                                textShadow: '0 1px 1px rgba(0,0,0,0.1)'
                                            }}>
                                            {row.weightedRisk}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Legend with Gradient Samples */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem', marginTop: '1.2rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                                <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'linear-gradient(90deg, #d1fae5, #14b8a6, #0d9488)', boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }} />
                                <span style={{ color: '#cbd5e1', fontSize: '0.75rem', fontWeight: 600 }}>Coverage: Light Teal → Deep Teal</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                                <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'linear-gradient(90deg, #fef3c7, #fcd34d, #d97706)', boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }} />
                                <span style={{ color: '#cbd5e1', fontSize: '0.75rem', fontWeight: 600 }}>Missing: Light Amber → Deep Orange</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem' }}>
                                <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: 'linear-gradient(90deg, #fce7f3, #f472b6, #be185d)', boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }} />
                                <span style={{ color: '#cbd5e1', fontSize: '0.75rem', fontWeight: 600 }}>Risk: Light Rose → Deep Plum</span>
                            </div>
                        </div>
                        <p style={{ color: '#94a3b8', fontSize: '0.73rem', marginTop: '0.8rem', fontStyle: 'italic' }}>✓ Color gradients represent magnitude: darker shades indicate higher values</p>
                    </div>
                    )}

                    {/* Section 3: Semantic Match Quality (Combined Block) */}
                    {activeViz === 'semantic' && (
                    <div className="content-card" style={{ background: '#1e293b', padding: '1.35rem', display: 'grid', gridTemplateColumns: '1fr 1.1fr', gap: '1.25rem', borderTop: `5px solid ${COLORS.info}` }}>

                        <div style={{ gridColumn: '1 / -1' }}>
                            <h3 style={{ margin: '0 0 0.5rem 0', display: 'flex', alignItems: 'center', gap: '10px', color: 'white' }}>
                                <Activity size={24} color={COLORS.info} />
                                Semantic Convergence & Match Quality Analysis
                            </h3>
                            <p style={{ margin: '0 0 1rem 0', color: '#94a3b8', fontSize: '0.95rem' }}>A detailed breakdown of how well the candidate's skills semantically align with the job requirements.</p>
                        </div>

                        {/* 8. Semantic Confidence Distribution */}
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <h4 style={{ margin: '0 0 1.5rem 0', color: '#cbd5e1', fontSize: '1.05rem', fontWeight: '600' }}>Confidence Distribution</h4>
                            <div style={{ height: 300, width: '100%' }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={buckets} margin={{ top: 10, right: 20, left: 0, bottom: 30 }}>
                                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" />
                                        <XAxis dataKey="range" tick={{ fontSize: 13, fill: 'white', fontWeight: 600 }} axisLine={false} tickLine={false} interval={0} angle={-15} textAnchor="end" height={60} />
                                        <YAxis allowDecimals={false} tick={{ fontSize: 13, fill: 'white', fontWeight: 600 }} axisLine={false} tickLine={false} />
                                        <Tooltip cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }} content={<CustomTooltip />} />
                                        <Bar dataKey="count" name="Skills" radius={[6, 6, 0, 0]} barSize={40}>
                                            {buckets.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={entry.fill} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* 7. Match Quality Ledger Table (4 Column Grid) */}
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <h4 style={{ margin: '0 0 1.5rem 0', color: '#cbd5e1', fontSize: '1.05rem', fontWeight: '600' }}>Detailed Match Ledger</h4>

                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem', width: '100%' }}>

                                {/* Exact Match Column */}
                                <div style={{ display: 'flex', flexDirection: 'column', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155', overflow: 'hidden' }}>
                                    <div style={{ background: '#10b98115', padding: '0.6rem', borderBottom: '2px solid #10b981', textAlign: 'center', fontWeight: 'bold', color: '#34d399', fontSize: '0.85rem' }}>Exact Matches (100%)</div>
                                    <div className="match-ledger-column" style={{ maxHeight: '210px', overflowY: 'auto', padding: '0.6rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                                        {(partition.exact_match || []).length > 0 ? (partition.exact_match || []).map((skill, i) => (
                                            <div key={i} style={{ background: '#1e293b', padding: '0.6rem', borderRadius: '8px', borderLeft: `4px solid #10b981`, boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <span style={{ fontWeight: '600', color: 'white', fontSize: '0.8rem' }}>{skill}</span>
                                                <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#10b981' }}>100%</span>
                                            </div>
                                        )) : <p style={{ color: '#94a3b8', fontSize: '0.8rem', textAlign: 'center', fontStyle: 'italic', margin: '0.75rem 0' }}>None</p>}
                                    </div>
                                </div>

                                {/* Strong Semantic Column */}
                                <div style={{ display: 'flex', flexDirection: 'column', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155', overflow: 'hidden' }}>
                                    <div style={{ background: '#3b82f615', padding: '0.6rem', borderBottom: '2px solid #3b82f6', textAlign: 'center', fontWeight: 'bold', color: '#60a5fa', fontSize: '0.85rem' }}>Strong (75-99%)</div>
                                    <div className="match-ledger-column" style={{ maxHeight: '210px', overflowY: 'auto', padding: '0.6rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                                        {(partition.strong_semantic || []).length > 0 ? Object.entries((partition.strong_semantic || []).reduce((acc, curr) => {
                                            const key = curr.similar_to || curr.skill;
                                            if (!acc[key]) acc[key] = { matches: [], maxScore: curr.score };
                                            acc[key].matches.push(curr.skill);
                                            if (curr.score > acc[key].maxScore) acc[key].maxScore = curr.score;
                                            return acc;
                                        }, {})).map(([jdSkill, data], i) => (
                                            <div key={i} style={{ background: '#1e293b', padding: '0.6rem', borderRadius: '8px', borderLeft: `4px solid #3b82f6`, boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <span style={{ fontWeight: '600', color: 'white', fontSize: '0.8rem' }}>{jdSkill}</span>
                                                    <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#3b82f6' }}>{data.maxScore ? (data.maxScore * 100).toFixed(0) : '85'}%</span>
                                                </div>
                                                <span style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Matched: {data.matches.join(', ')}</span>
                                            </div>
                                        )) : <p style={{ color: '#94a3b8', fontSize: '0.8rem', textAlign: 'center', fontStyle: 'italic', margin: '0.75rem 0' }}>None</p>}
                                    </div>
                                </div>

                                {/* Moderate Semantic Column */}
                                <div style={{ display: 'flex', flexDirection: 'column', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155', overflow: 'hidden' }}>
                                    <div style={{ background: '#f59e0b15', padding: '0.6rem', borderBottom: '2px solid #f59e0b', textAlign: 'center', fontWeight: 'bold', color: '#fbbf24', fontSize: '0.85rem' }}>Moderate (50-74%)</div>
                                    <div className="match-ledger-column" style={{ maxHeight: '210px', overflowY: 'auto', padding: '0.6rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                                        {(partition.moderate_semantic || []).length > 0 ? Object.entries((partition.moderate_semantic || []).reduce((acc, curr) => {
                                            const key = curr.similar_to || curr.skill;
                                            if (!acc[key]) acc[key] = { matches: [], maxScore: curr.score };
                                            acc[key].matches.push(curr.skill);
                                            if (curr.score > acc[key].maxScore) acc[key].maxScore = curr.score;
                                            return acc;
                                        }, {})).map(([jdSkill, data], i) => (
                                            <div key={i} style={{ background: '#1e293b', padding: '0.6rem', borderRadius: '8px', borderLeft: `4px solid #f59e0b`, boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <span style={{ fontWeight: '600', color: 'white', fontSize: '0.8rem' }}>{jdSkill}</span>
                                                    <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#f59e0b' }}>{data.maxScore ? (data.maxScore * 100).toFixed(0) : '65'}%</span>
                                                </div>
                                                <span style={{ fontSize: '0.65rem', color: '#94a3b8' }}>Matched: {data.matches.join(', ')}</span>
                                            </div>
                                        )) : <p style={{ color: '#94a3b8', fontSize: '0.8rem', textAlign: 'center', fontStyle: 'italic', margin: '0.75rem 0' }}>None</p>}
                                    </div>
                                </div>

                                {/* Missing Column */}
                                <div style={{ display: 'flex', flexDirection: 'column', background: '#0f172a', borderRadius: '12px', border: '1px solid #334155', overflow: 'hidden' }}>
                                    <div style={{ background: '#ef444415', padding: '0.6rem', borderBottom: '2px solid #ef4444', textAlign: 'center', fontWeight: 'bold', color: '#f87171', fontSize: '0.85rem' }}>Missing (0%)</div>
                                    <div className="match-ledger-column" style={{ maxHeight: '210px', overflowY: 'auto', padding: '0.6rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                                        {(missingFromResume || []).length > 0 ? (missingFromResume || []).map((match, i) => (
                                            <div key={i} style={{ background: '#1e293b', padding: '0.6rem', borderRadius: '8px', borderLeft: `4px solid #ef4444`, boxShadow: '0 1px 2px rgba(0,0,0,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <span style={{ fontWeight: '600', color: 'white', fontSize: '0.8rem', opacity: 0.7 }}>{match.skill || match}</span>
                                                <span style={{ fontSize: '0.7rem', fontWeight: 'bold', color: '#ef4444' }}>0%</span>
                                            </div>
                                        )) : <p style={{ color: '#94a3b8', fontSize: '0.8rem', textAlign: 'center', fontStyle: 'italic', margin: '0.75rem 0' }}>None</p>}
                                    </div>
                                </div>

                            </div>
                        </div>
                    </div>
                    )}

                    {/* Section 4: Enhanced Category Skill Domain Visualization */}
                    {activeViz === 'domain' && (
                    <div
                        className={`content-card ${skillsMapVisible ? 'is-visible' : ''}`}
                        style={{
                            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
                            borderTop: '5px solid #06b6d4',
                            padding: '1.35rem',
                            boxShadow: '0 10px 30px rgba(0,0,0,0.3)',
                            borderRadius: '16px'
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1.5rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
                            <div>
                                <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '12px', color: '#f1f5f9', fontSize: '1.2rem', fontWeight: 900, letterSpacing: '0.3px' }}>
                                    <div style={{ background: 'rgba(6, 182, 212, 0.2)', padding: '0.5rem', borderRadius: '10px' }}>
                                        <Layers size={24} color="#06b6d4" />
                                    </div>
                                    Domain Skill Categories
                                </h3>
                                <p style={{ margin: '0.4rem 0 0', color: '#94a3b8', fontSize: '0.85rem' }}>Interactive skill inventory across {treemapTiles.length} professional domains</p>
                            </div>
                            <div className="category-skill-legend" style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                                <span className="legend-chip legend-exact">✓ Exact</span>
                                <span className="legend-chip legend-strong">⬆ Strong</span>
                                <span className="legend-chip legend-moderate">→ Moderate</span>
                                <span className="legend-chip legend-missing">✗ Missing</span>
                            </div>
                        </div>

                        <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '12px', padding: '0.85rem', marginBottom: '1.1rem', border: '1px solid rgba(6,182,212,0.2)' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                                    <div style={{ background: 'rgba(6,182,212,0.15)', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.9rem', fontWeight: 700, color: '#22d3ee' }}>Total Categories</div>
                                    <span style={{ fontSize: '1.3rem', fontWeight: 900, color: '#f1f5f9' }}>{treemapTiles.length}</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                                    <div style={{ background: 'rgba(34,197,94,0.15)', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.9rem', fontWeight: 700, color: '#86efac' }}>Avg Coverage</div>
                                    <span style={{ fontSize: '1.3rem', fontWeight: 900, color: '#f1f5f9' }}>{Math.round(treemapTiles.reduce((sum, t) => sum + t.coverage, 0) / Math.max(1, treemapTiles.length))}%</span>
                                </div>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                                    <div style={{ background: 'rgba(239,68,68,0.15)', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.9rem', fontWeight: 700, color: '#fca5a5' }}>Total Skills</div>
                                    <span style={{ fontSize: '1.3rem', fontWeight: 900, color: '#f1f5f9' }}>{treemapTiles.reduce((sum, t) => sum + t.total, 0)}</span>
                                </div>
                            </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '0.6rem', width: '100%' }}>
                            {treemapTiles.length > 0 ? (
                                treemapTiles.map((item, categoryIndex) => {
                                    const coveragePercent = item.coverage;
                                    const coverageColor = coveragePercent >= 80 ? '#10b981' : coveragePercent >= 50 ? '#f59e0b' : '#ef4444';
                                    const coverageOpacity = coveragePercent >= 80 ? 0.2 : coveragePercent >= 50 ? 0.2 : 0.2;
                                    const categoryGradients = [
                                        { from: '#0ea5e9', to: '#0369a1' },
                                        { from: '#10b981', to: '#047857' },
                                        { from: '#f59e0b', to: '#d97706' },
                                        { from: '#8b5cf6', to: '#6d28d9' },
                                        { from: '#ec4899', to: '#be185d' },
                                        { from: '#06b6d4', to: '#0891b2' },
                                        { from: '#3b82f6', to: '#1d4ed8' },
                                        { from: '#14b8a6', to: '#0d9488' },
                                    ];
                                    const gradient = categoryGradients[categoryIndex % categoryGradients.length];

                                    return (
                                        <div
                                            key={`${item.category}-${categoryIndex}`}
                                            style={{
                                                background: `linear-gradient(135deg, ${gradient.from}${coverageOpacity ? '25' : '10'} 0%, ${gradient.to}${coverageOpacity ? '08' : '03'} 100%)`,
                                                border: `2px solid ${gradient.from}50`,
                                                borderRadius: '14px',
                                                padding: '0.75rem',
                                                boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
                                                transition: 'all 0.3s cubic-bezier(0.22, 1, 0.36, 1)',
                                                opacity: 1,
                                                transform: 'translateY(0) scale(1)',
                                                animation: `boxFallIn 0.65s cubic-bezier(0.22, 1, 0.36, 1) ${categoryIndex * 75}ms forwards`
                                            }}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                                                <div style={{ flex: 1 }}>
                                                    <h4 style={{ margin: 0, color: '#f1f5f9', fontSize: '0.95rem', fontWeight: 900, letterSpacing: '0.3px' }}>
                                                        {item.category}
                                                    </h4>
                                                    <p style={{ margin: '0.22rem 0 0', color: '#cbd5e1', fontSize: '0.74rem', fontWeight: 600 }}>
                                                        {item.total} skills • {item.coverage}% coverage
                                                    </p>
                                                </div>
                                                <div style={{ 
                                                    background: `rgba(${coverageColor.includes('10b981') ? '16,185,129' : coverageColor.includes('f59e0b') ? '245,158,11' : '239,68,68'}, 0.2)`,
                                                    padding: '0.38rem 0.62rem',
                                                    borderRadius: '10px',
                                                    textAlign: 'right',
                                                    minWidth: '58px'
                                                }}>
                                                    <div style={{ fontSize: '1rem', fontWeight: 900, color: coverageColor }}>
                                                        {item.present}/{item.total}
                                                    </div>
                                                    <div style={{ fontSize: '0.64rem', color: '#cbd5e1', marginTop: '0.12rem' }}>matched</div>
                                                </div>
                                            </div>

                                            {/* Coverage Progress Bar */}
                                            <div style={{ background: 'rgba(0,0,0,0.2)', borderRadius: '8px', height: '5px', marginBottom: '0.72rem', overflow: 'hidden' }}>
                                                <div style={{
                                                    background: `linear-gradient(90deg, ${gradient.from}, ${gradient.to})`,
                                                    height: '100%',
                                                    width: `${item.coverage}%`,
                                                    borderRadius: '8px',
                                                    transition: 'width 0.6s ease'
                                                }} />
                                            </div>

                                            <div className="skill-mini-grid" style={{
                                                display: 'grid',
                                                gridTemplateColumns: 'repeat(auto-fill, minmax(78px, 1fr))',
                                                gap: '0.5rem',
                                                marginTop: '0.58rem'
                                            }}>
                                                {item.skillItems.map((skillItem, skillIndex) => {
                                                    const statusColors = {
                                                        exact: { bg: '#86efac', bgLight: 'rgba(16,185,129,0.15)', border: 'rgba(16,185,129,0.5)' },
                                                        strong: { bg: '#93c5fd', bgLight: 'rgba(59,130,246,0.15)', border: 'rgba(59,130,246,0.5)' },
                                                        moderate: { bg: '#fcd34d', bgLight: 'rgba(245,158,11,0.15)', border: 'rgba(245,158,11,0.5)' },
                                                        missing: { bg: '#fca5a5', bgLight: 'rgba(239,68,68,0.15)', border: 'rgba(239,68,68,0.5)' }
                                                    };
                                                    const colors = statusColors[skillItem.status] || statusColors.moderate;

                                                    return (
                                                        <div
                                                            key={`${item.category}-${skillItem.skill}-${skillIndex}`}
                                                            className={`skill-mini-box ${skillItem.status}`}
                                                            style={{
                                                                background: colors.bgLight,
                                                                border: `1.5px solid ${colors.border}`,
                                                                color: colors.bg,
                                                                borderRadius: '8px',
                                                                padding: '0.36rem 0.45rem',
                                                                fontSize: '0.7rem',
                                                                fontWeight: 700,
                                                                textAlign: 'center',
                                                                minHeight: '30px',
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                                justifyContent: 'center',
                                                                lineHeight: 1.2,
                                                                overflow: 'hidden',
                                                                textOverflow: 'ellipsis',
                                                                whiteSpace: 'normal',
                                                                wordBreak: 'break-word',
                                                                transition: 'all 0.3s ease',
                                                                boxShadow: '0 2px 6px rgba(0,0,0,0.1)',
                                                                animation: `boxFallIn 0.6s cubic-bezier(0.22, 1, 0.36, 1) ${(categoryIndex * 75) + (skillIndex * 18)}ms forwards`,
                                                                cursor: 'default'
                                                            }}
                                                            title={`${skillItem.skill} (${skillItem.status})`}
                                                        >
                                                            {skillItem.skill}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    );
                                })
                            ) : (
                                <div style={{ gridColumn: '1 / -1', color: '#94a3b8', fontStyle: 'italic', textAlign: 'center', padding: '2rem', fontSize: '0.95rem' }}>
                                    📊 No category/skill map available for this run.
                                </div>
                            )}
                        </div>
                    </div>
                    )}

                </div>
            </div>
    );

    if (isEmbedded) {
        return panelContent;
    }

    const modalContent = (
        <div className="modal-overlay" style={{ zIndex: 10000, background: 'rgba(0,0,0,0.85)' }}>
            {panelContent}
        </div>
    );

    return ReactDOM.createPortal(modalContent, document.body);
};

export default VisualizationModal;
