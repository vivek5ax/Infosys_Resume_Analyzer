import React from 'react';

const imageModules = import.meta.glob('../assets/landing/*.{png,jpg,jpeg,webp,gif,avif,svg}', {
    eager: true,
    import: 'default',
});

const orderedImages = Object.entries(imageModules)
    .sort(([pathA], [pathB]) => pathA.localeCompare(pathB, undefined, { numeric: true }))
    .map(([, src]) => src);

function LandingPage({ onStart }) {
    const sliderImages = orderedImages.length > 1 ? [...orderedImages, ...orderedImages] : orderedImages;
    const durationSeconds = Math.max(16, orderedImages.length * 4);

    const landingSteps = [
        { number: '1', title: 'Choose a domain', description: 'Pick the target role domain that best fits the hiring need.' },
        { number: '2', title: 'Upload JD details', description: 'Upload a job description file or paste the text directly.' },
        { number: '3', title: 'Add resume', description: 'Attach a candidate resume in PDF, DOCX, or TXT format.' },
        { number: '4', title: 'Run the analysis', description: 'Start the AI match to reveal skills alignment and gaps.' },
        { number: '5', title: 'Review results', description: 'See scorecards, missing capabilities, and evidence snapshots.' },
        { number: '6', title: 'Export report', description: 'Download a polished PDF recruiter report from the sidebar.' },
    ];

    return (
        <div className="landing-page fade-in">
            <section className="landing-hero-card">
                <div className="landing-hero-header">
                    <div className="landing-hero-copy">
                        <p className="landing-kicker">Resume Analyzer</p>
                        <h1 className="landing-title">A smarter way to screen resumes and JDs</h1>
                        <p className="landing-tagline">
                            Analyze candidate resumes against job requirements with AI-powered alignment, skills highlights, and recruiter-ready insights.
                        </p>
                        <div className="landing-actions landing-actions-inline">
                            <button className="landing-start-btn" onClick={onStart}>Start Analysis</button>
                        </div>
                    </div>

                    <div className="landing-step-panel">
                        <div className="landing-step-grid">
                            {landingSteps.map(step => (
                                <article key={step.number} className="landing-step-card">
                                    <div className="landing-step-marker">{step.number}</div>
                                    <h3 className="landing-step-title">{step.title}</h3>
                                    <p className="landing-step-description">{step.description}</p>
                                </article>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="landing-slider-shell" aria-label="Project flow image slider">
                    {orderedImages.length === 0 ? (
                        <div className="landing-slider-empty">
                            Add ordered screenshots to src/assets/landing (for example 01-upload.png, 02-extract.png, 03-match.png)
                            to enable the flow slider.
                        </div>
                    ) : (
                        <div
                            className="landing-slider-track"
                            style={{ animationDuration: `${durationSeconds}s` }}
                        >
                            {sliderImages.map((src, idx) => (
                                <figure className="landing-slide" key={`${src}-${idx}`}>
                                    <img src={src} alt={`Project flow step ${idx + 1}`} loading="lazy" />
                                </figure>
                            ))}
                        </div>
                    )}
                </div>
            </section>
        </div>
    );
}

export default LandingPage;
