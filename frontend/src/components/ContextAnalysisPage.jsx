import React from 'react';
import { BrainCircuit, CheckCircle, AlertTriangle, XCircle, Info } from 'lucide-react';

const ContextAnalysisPage = ({ data }) => {
    if (!data || !data.context_analysis) {
        return (
            <section className="documents-panel fade-in neo-panel">
                <div className="results-empty" style={{ textAlign: 'center', padding: '3rem', color: '#64748b' }}>
                    <BrainCircuit size={48} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
                    <h3 style={{ fontSize: '1.2rem', fontWeight: 600, margin: '0 0 0.5rem 0' }}>No Context Analysis Available</h3>
                    <p>Run an assessment to view deep semantic and implicit skill analysis.</p>
                </div>
            </section>
        );
    }

    const { context_summary, context_validations = [] } = data.context_analysis;

    // Group validations by type for organized display
    const implicitMatches = context_validations.filter(v => v.analysis_type === 'Implicit Match');
    const validatedMatches = context_validations.filter(v => v.analysis_type === 'Contextually Validated');
    const actualGaps = context_validations.filter(v => v.analysis_type === 'Actual Gap');
    const falsePositives = context_validations.filter(v => v.analysis_type === 'False Positive');
    const additionalSkills = context_validations.filter(v => v.analysis_type === 'Additional Skill');

    const renderCard = (val, idx, colorTheme) => (
        <div key={idx} style={{ 
            background: '#ffffff', 
            borderRadius: '12px', 
            padding: '1.25rem', 
            border: `1px solid ${colorTheme.border}`,
            boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03)',
            marginBottom: '1rem'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.2rem', borderBottom: `1px solid #f1f5f9`, paddingBottom: '0.8rem' }}>
                <h4 style={{ margin: 0, color: '#1e293b', fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {colorTheme.icon}
                    {val.skill_name}
                </h4>
                <span style={{ 
                    background: colorTheme.badgeBg, 
                    color: colorTheme.badgeColor, 
                    padding: '0.35rem 0.85rem', 
                    borderRadius: '999px', 
                    fontSize: '0.8rem', 
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.02em'
                }}>
                    {val.analysis_type}
                </span>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.25rem', marginBottom: '1.25rem' }}>
                <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', borderLeft: '4px solid #cbd5e1' }}>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: 800 }}>Required in Job Description</div>
                    <div style={{ fontSize: '0.95rem', color: '#334155', lineHeight: '1.5' }}>{val.jd_context}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', borderLeft: `4px solid ${colorTheme.badgeColor}` }}>
                    <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: 800 }}>Found in Resume Context</div>
                    <div style={{ fontSize: '0.95rem', color: '#334155', lineHeight: '1.5' }}>{val.resume_context || "No supporting context found."}</div>
                </div>
            </div>

            <div style={{ background: '#f0fdfa', padding: '1rem', borderRadius: '8px', border: '1px solid #ccfbf1' }}>
                <div style={{ fontSize: '0.75rem', color: '#0d9488', marginBottom: '0.5rem', textTransform: 'uppercase', fontWeight: 800 }}>AI Reasoning</div>
                <div style={{ fontSize: '0.95rem', color: '#115e59', lineHeight: '1.5' }}>{val.reasoning}</div>
            </div>
        </div>
    );

    return (
        <section className="documents-panel fade-in neo-panel" style={{ padding: '1.5rem', background: '#f1f5f9', overflowY: 'auto' }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                
                {/* Header Summary */}
                <div style={{ 
                    background: '#ffffff', 
                    borderRadius: '16px', 
                    padding: '1.5rem 2rem',
                    marginBottom: '2rem',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05)'
                }}>
                    <h2 style={{ margin: '0 0 1rem 0', color: '#0f172a', fontSize: '1.5rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div style={{ background: '#eff6ff', padding: '0.6rem', borderRadius: '12px', color: '#3b82f6' }}>
                            <BrainCircuit size={28} />
                        </div>
                        Context Analysis Engine
                    </h2>
                    <p style={{ margin: 0, color: '#475569', fontSize: '1.05rem', lineHeight: '1.6' }}>
                        {context_summary || "The Context Analysis engine reads deep into the text to discover hidden skills and validate semantic matches beyond simple keyword extraction."}
                    </p>
                </div>

                {/* Categories */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '2.5rem' }}>
                    
                    {implicitMatches.length > 0 && (
                        <section>
                            <h3 style={{ color: '#15803d', fontSize: '1.25rem', marginBottom: '1rem', borderBottom: '2px solid #bbf7d0', paddingBottom: '0.5rem' }}>
                                ✨ Implicit Matches Discovered ({implicitMatches.length})
                            </h3>
                            {implicitMatches.map((val, idx) => renderCard(val, idx, {
                                badgeBg: '#dcfce7', badgeColor: '#166534', border: '#bbf7d0', icon: <CheckCircle size={20} color="#166534" />
                            }))}
                        </section>
                    )}

                    {validatedMatches.length > 0 && (
                        <section>
                            <h3 style={{ color: '#15803d', fontSize: '1.25rem', marginBottom: '1rem', borderBottom: '2px solid #bbf7d0', paddingBottom: '0.5rem' }}>
                                ✅ Contextually Validated Strengths ({validatedMatches.length})
                            </h3>
                            {validatedMatches.map((val, idx) => renderCard(val, idx, {
                                badgeBg: '#dcfce7', badgeColor: '#166534', border: '#bbf7d0', icon: <CheckCircle size={20} color="#166534" />
                            }))}
                        </section>
                    )}

                    {actualGaps.length > 0 && (
                        <section>
                            <h3 style={{ color: '#b91c1c', fontSize: '1.25rem', marginBottom: '1rem', borderBottom: '2px solid #fecaca', paddingBottom: '0.5rem' }}>
                                ❌ Confirmed Gaps ({actualGaps.length})
                            </h3>
                            {actualGaps.map((val, idx) => renderCard(val, idx, {
                                badgeBg: '#fee2e2', badgeColor: '#991b1b', border: '#fecaca', icon: <XCircle size={20} color="#991b1b" />
                            }))}
                        </section>
                    )}

                    {falsePositives.length > 0 && (
                        <section>
                            <h3 style={{ color: '#b45309', fontSize: '1.25rem', marginBottom: '1rem', borderBottom: '2px solid #fde68a', paddingBottom: '0.5rem' }}>
                                ⚠️ False Positives Corrected ({falsePositives.length})
                            </h3>
                            {falsePositives.map((val, idx) => renderCard(val, idx, {
                                badgeBg: '#fef3c7', badgeColor: '#b45309', border: '#fde68a', icon: <AlertTriangle size={20} color="#b45309" />
                            }))}
                        </section>
                    )}

                    {additionalSkills.length > 0 && (
                        <section>
                            <h3 style={{ color: '#6b21a8', fontSize: '1.25rem', marginBottom: '1rem', borderBottom: '2px solid #e9d5ff', paddingBottom: '0.5rem' }}>
                                💡 Additional Skills Found ({additionalSkills.length})
                            </h3>
                            {additionalSkills.map((val, idx) => renderCard(val, idx, {
                                badgeBg: '#f3e8ff', badgeColor: '#7e22ce', border: '#e9d5ff', icon: <Info size={20} color="#7e22ce" />
                            }))}
                        </section>
                    )}

                </div>

            </div>
        </section>
    );
};

export default ContextAnalysisPage;
