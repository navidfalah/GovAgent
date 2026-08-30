/* GovAgents Frontend Application Logic */

'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let currentAssessmentId = null;
let currentEventSource = null;
let assessmentHistory = [];

// ── Example Proposals ────────────────────────────────────────────────────────
const EXAMPLES = {
  monitor: {
    title: 'Employee Productivity Monitoring AI',
    description: 'A company wants to deploy an AI system that analyzes all employee communications (Slack, email, calendar) to automatically generate daily productivity scores and flag underperforming employees to HR managers. The system uses NLP to detect sentiment, topic frequency, and response times to compute a composite productivity metric.',
    organization: 'Acme Corp',
    sector: 'enterprise',
    context: 'Internal HR system deployed to 2,000 employees across EU offices',
    tech: 'BERT-based NLP model fine-tuned on communication data. Daily batch processing. Scores stored in HR database. Manager dashboard with employee-level detail.'
  },
  medical: {
    title: 'AI Medical Diagnosis Assistant',
    description: 'A hospital network plans to deploy an AI system that analyzes medical imaging (X-rays, CT scans) to assist radiologists in diagnosing lung cancer. The system produces confidence-scored diagnoses that are flagged for radiologist review. High-confidence negative results may be released without additional review in non-critical cases.',
    organization: 'HealthNet Hospital Group',
    sector: 'healthcare',
    context: 'Radiology departments in 12 EU hospitals processing 500+ scans daily',
    tech: 'CNN-based image classification (ResNet-50 fine-tuned). Integrated into PACS. 94% sensitivity on internal test set. FDA 510(k) clearance pending.'
  },
  recruitment: {
    title: 'AI Recruitment Screening System',
    description: 'An HR tech startup wants to offer an AI service that automatically screens job applications by analyzing CVs, cover letters, and LinkedIn profiles to rank candidates and recommend which ones to advance to interview. The system is trained on historical successful hire data from client organizations.',
    organization: 'TalentAI GmbH',
    sector: 'enterprise',
    context: 'SaaS platform offered to 50+ EU-based enterprise clients for high-volume recruitment',
    tech: 'Multi-modal ML model combining NLP (CV parsing) and structured feature extraction. Trained on 100k historical hiring decisions. REST API integration with ATS systems.'
  },
  chatbot: {
    title: 'Customer Service AI Chatbot',
    description: 'A retail bank wants to deploy an AI chatbot to handle customer service inquiries. The chatbot can answer FAQs, help with account management, and provide basic financial guidance. It escalates complex issues to human agents. The chatbot retains conversation history for 12 months for quality improvement.',
    organization: 'NextBank SA',
    sector: 'finance',
    context: 'Public-facing web and mobile app serving 1.5M retail banking customers in France',
    tech: 'GPT-4 based chatbot with RAG over bank knowledge base. PII detection layer. Conversation logging to compliance-grade storage.'
  }
};

// ── Initialization ────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadCorpusStatus();
  loadHistory();
});

// ── Navigation ────────────────────────────────────────────────────────────────
function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`section${cap(name)}`).classList.add('active');
  document.getElementById(`nav${cap(name)}`).classList.add('active');

  if (name === 'policies') loadPolicies();
  if (name === 'history') loadHistory();
  if (name === 'settings') loadConfig();
}

function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

// ── Corpus Status ─────────────────────────────────────────────────────────────
async function loadCorpusStatus() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    const el = document.getElementById('corpusChunks');
    if (data.corpus_ready) {
      el.textContent = `${data.corpus_chunks} policy chunks`;
      document.querySelector('.status-dot').style.background = 'var(--accent-emerald)';
    } else {
      el.textContent = 'Corpus empty';
      document.querySelector('.status-dot').style.background = 'var(--accent-amber)';
    }
  } catch {
    document.getElementById('corpusChunks').textContent = 'API offline';
    document.querySelector('.status-dot').style.background = 'var(--accent-rose)';
  }
}

// ── Example Loader ────────────────────────────────────────────────────────────
function loadExample(key) {
  const e = EXAMPLES[key];
  if (!e) return;
  document.getElementById('propTitle').value = e.title;
  document.getElementById('propDesc').value = e.description;
  document.getElementById('propOrg').value = e.organization;
  document.getElementById('propSector').value = e.sector;
  document.getElementById('propContext').value = e.context;
  document.getElementById('propTech').value = e.tech;
  document.getElementById('propTitle').focus();
}

// ── Assessment Submission ─────────────────────────────────────────────────────
async function submitAssessment(event) {
  event.preventDefault();

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner"></div> Running Assessment...`;

  // Read file if uploaded
  let fileText = '';
  const fileInput = document.getElementById('propFile');
  if (fileInput.files.length > 0) {
    try {
      fileText = await fileInput.files[0].text();
    } catch (e) {
      console.warn("Failed to read file", e);
    }
  }

  const payload = {
    title: document.getElementById('propTitle').value.trim(),
    description: document.getElementById('propDesc').value.trim() + (fileText ? `\n\n[UPLOADED CONTEXT]\n${fileText.substring(0, 10000)}` : ''),
    organization: document.getElementById('propOrg').value.trim() || null,
    sector: document.getElementById('propSector').value || null,
    deployment_context: document.getElementById('propContext').value.trim() || null,
    technical_details: document.getElementById('propTech').value.trim() || null,
    pipeline_config: {
      policy: {
        enabled: document.getElementById('cfgPolicyEnabled').checked,
        max_requirements: parseInt(document.getElementById('cfgPolicyMax').value, 10)
      },
      compliance: {
        enabled: document.getElementById('cfgComplianceEnabled').checked,
        strictness: document.getElementById('cfgComplianceStrictness').value
      },
      risk: {
        enabled: document.getElementById('cfgRiskEnabled').checked,
        risk_tolerance: document.getElementById('cfgRiskTolerance').value
      },
      ethics: {
        enabled: document.getElementById('cfgEthicsEnabled').checked,
        focus_areas: document.getElementById('cfgEthicsFocus').value === 'all' ? [] : [document.getElementById('cfgEthicsFocus').value]
      },
      technical: {
        enabled: document.getElementById('cfgTechnicalEnabled').checked,
        deep_scan: document.querySelector('input[name="cfgTechScan"]:checked').value === 'true'
      },
      privacy: {
        enabled: document.getElementById('cfgPrivacyEnabled').checked,
        strict_gdpr: document.querySelector('input[name="cfgPrivacyGdpr"]:checked').value === 'true'
      },
      security: {
        enabled: document.getElementById('cfgSecurityEnabled').checked,
        threat_model: document.getElementById('cfgSecurityThreat').value
      },
      bias: {
        enabled: document.getElementById('cfgBiasEnabled').checked,
        fairness_metric: document.getElementById('cfgBiasMetric').value
      },
      guardrail: {
        enabled: document.getElementById('cfgGuardrailEnabled').checked,
        strictness: document.getElementById('cfgGuardrailAction').value
      }
    }
  };

  try {
    const res = await fetch('/api/assess', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      let errorMsg = 'Failed to submit assessment';
      if (err.detail) {
        if (Array.isArray(err.detail)) {
          errorMsg = err.detail.map(e => e.msg).join(', ');
        } else {
          errorMsg = err.detail;
        }
      }
      throw new Error(errorMsg);
    }

    const data = await res.json();
    currentAssessmentId = data.assessment_id;

    // Configure pipeline UI paths based on toggles
    document.getElementById('agent-policy').style.opacity = payload.pipeline_config.policy.enabled ? '1' : '0.2';
    document.getElementById('agent-compliance').style.opacity = payload.pipeline_config.compliance.enabled ? '1' : '0.2';
    document.getElementById('agent-risk').style.opacity = payload.pipeline_config.risk.enabled ? '1' : '0.2';
    document.getElementById('agent-ethics').style.opacity = payload.pipeline_config.ethics.enabled ? '1' : '0.2';
    document.getElementById('agent-technical').style.opacity = payload.pipeline_config.technical.enabled ? '1' : '0.2';
    document.getElementById('agent-security').style.opacity = payload.pipeline_config.security.enabled ? '1' : '0.2';
    document.getElementById('agent-privacy').style.opacity = payload.pipeline_config.privacy.enabled ? '1' : '0.2';
    document.getElementById('agent-bias').style.opacity = payload.pipeline_config.bias.enabled ? '1' : '0.2';
    document.getElementById('agent-guardrail').style.opacity = payload.pipeline_config.guardrail.enabled ? '1' : '0.2';

    // Show pipeline, hide form
    document.getElementById('formCard').classList.add('hidden');
    showPipeline();

    // Connect to SSE stream
    connectToStream(data.assessment_id);
    
    showToast('Assessment submitted successfully! Starting pipeline...', 'success');
    logActivity('system', 'Assessment pipeline started');

  } catch (err) {
    showToast(`Error: ${err.message}`, 'error');
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Run Governance Assessment`;
  }
}

// ── Pipeline UI ───────────────────────────────────────────────────────────────
function showPipeline() {
  const card = document.getElementById('pipelineCard');
  card.classList.remove('hidden');
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function toggleCard(cardId, isEnabled) {
  const card = document.getElementById(cardId);
  if (!card) return;
  if (isEnabled) {
    card.classList.remove('disabled');
  } else {
    card.classList.add('disabled');
  }
}

function updateAgentState(agentName, state, message) {
  const node = document.getElementById(`agent-${agentName}`);
  if (!node) return;
  node.className = `agent-node${agentName === 'governance' ? ' governance-node' : ''} ${state}`;
  const statusEl = node.querySelector('.agent-status');
  statusEl.className = `agent-status ${state}`;
  statusEl.textContent = state === 'running' ? 'Running...' : state === 'complete' ? 'Done ✓' : 'Waiting';
}

function updatePipelineStatus(text, done = false) {
  const el = document.getElementById('pipelineStatusText');
  el.textContent = text;
  const spinner = document.querySelector('.pipeline-status .spinner');
  if (done && spinner) spinner.style.display = 'none';
}

const AGENT_COLORS = {
  policy: 'agent-color-policy',
  risk: 'agent-color-risk',
  technical: 'agent-color-technical',
  compliance: 'agent-color-compliance',
  ethics: 'agent-color-ethics',
  governance: 'agent-color-governance',
};

function logActivity(agent, message) {
  const container = document.getElementById('activityEntries');
  const now = new Date().toLocaleTimeString('en-GB', { hour12: false });
  const colorClass = AGENT_COLORS[agent] || 'agent-color-system';
  const agentLabel = agent === 'system' ? '[system]' : `[${agent}]`;

  const entry = document.createElement('div');
  entry.className = 'activity-entry';
  entry.innerHTML = `
    <span class="activity-time">${now}</span>
    <span class="activity-agent ${colorClass}">${agentLabel}</span>
    <span class="activity-msg">${message}</span>
  `;
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
}

// ── SSE Streaming ─────────────────────────────────────────────────────────────
function connectToStream(assessmentId) {
  if (currentEventSource) {
    currentEventSource.close();
  }

  const evtSource = new EventSource(`/api/assess/${assessmentId}/stream`);
  currentEventSource = evtSource;

  evtSource.addEventListener('connected', () => {
    logActivity('system', 'Connected to assessment stream');
  });

  evtSource.addEventListener('phase_start', (e) => {
    const d = JSON.parse(e.data);
    const phaseName = d.phase.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    updatePipelineStatus(d.phase_num ? `Phase ${d.phase_num}: ${phaseName}` : phaseName);
    logActivity('system', `▶ ${d.phase_num ? `Phase ${d.phase_num}: ` : ''}${phaseName}`);
  });

  evtSource.addEventListener('agent_start', (e) => {
    const d = JSON.parse(e.data);
    if (d.agent) {
      updateAgentState(d.agent, 'running');
      logActivity(d.agent, d.message || 'Starting...');
    }
  });

  evtSource.addEventListener('agent_complete', (e) => {
    const d = JSON.parse(e.data);
    if (d.agent) {
      updateAgentState(d.agent, 'complete');
      logActivity(d.agent, `✓ ${d.message || 'Complete'}`);
      
      // Hide subagent UI if any
      const subagentNode = document.getElementById(`subagent-${d.agent}`);
      if (subagentNode) {
        subagentNode.style.display = 'none';
      }
    }
  });

  evtSource.addEventListener('subagent_spawned', (e) => {
    const d = JSON.parse(e.data);
    if (d.agent) {
      logActivity(`${d.agent}-sub`, `🔍 Searching: ${d.query}`);
      // Show subagent node
      const parentNode = document.getElementById(`agent-${d.agent}`);
      if (parentNode) {
        let subNode = document.getElementById(`subagent-${d.agent}`);
        if (!subNode) {
          subNode = document.createElement('div');
          subNode.id = `subagent-${d.agent}`;
          subNode.className = 'subagent-node';
          subNode.innerHTML = `
            <div class="spinner" style="width: 10px; height: 10px; border-width: 2px; display: inline-block;"></div>
            <span style="font-size: 0.6rem; color: var(--text-muted);">Researching...</span>
          `;
          parentNode.appendChild(subNode);
        }
        subNode.style.display = 'flex';
      }
    }
  });

  evtSource.addEventListener('subagent_complete', (e) => {
    const d = JSON.parse(e.data);
    if (d.agent) {
      logActivity(`${d.agent}-sub`, `✅ Found ${d.findings} facts (Certainty: ${d.certainty}) for: ${d.query}`);
    }
  });

  evtSource.addEventListener('debate_start', (e) => {
    const d = JSON.parse(e.data);
    logActivity('system', `⚡ ${d.message || 'Debate protocol activated'}`);
  });

  evtSource.addEventListener('debate_complete', (e) => {
    const d = JSON.parse(e.data);
    logActivity('system', `✓ ${d.message || 'Debate resolved'}`);
  });

  evtSource.addEventListener('ping', () => {});

  evtSource.addEventListener('done', async (e) => {
    const d = JSON.parse(e.data);
    evtSource.close();
    updatePipelineStatus('Assessment complete ✓', true);
    logActivity('system', `Assessment complete — fetching report...`);

    // Load and render full report
    await loadAndRenderReport(assessmentId);
    loadHistory();
    loadCorpusStatus();
  });

  evtSource.addEventListener('error', (e) => {
    let msg = 'Unknown error';
    try { msg = JSON.parse(e.data).error; } catch {}
    logActivity('system', `❌ Error: ${msg}`);
    evtSource.close();
    updatePipelineStatus('Assessment failed', true);
    showToast(`Pipeline Error: ${msg}`, 'error');
    restoreForm();
  });

  evtSource.onerror = () => {
    // Connection error (might happen if server restarts)
    logActivity('system', 'Stream connection lost — polling for result...');
    evtSource.close();
    pollForCompletion(assessmentId);
  };
}

async function pollForCompletion(assessmentId, attempts = 0) {
  if (attempts > 60) return; // Stop after 5 minutes
  await new Promise(r => setTimeout(r, 5000));
  try {
    const res = await fetch(`/api/assess/${assessmentId}`);
    const data = await res.json();
    if (data.status === 'completed') {
      await loadAndRenderReport(assessmentId);
      loadHistory();
    } else if (data.status === 'failed') {
      logActivity('system', `❌ Assessment failed: ${data.error}`);
      restoreForm();
    } else {
      pollForCompletion(assessmentId, attempts + 1);
    }
  } catch {
    pollForCompletion(assessmentId, attempts + 1);
  }
}

// ── Report Rendering ──────────────────────────────────────────────────────────
async function loadAndRenderReport(assessmentId) {
  try {
    const res = await fetch(`/api/assess/${assessmentId}`);
    const record = await res.json();
    if (record.report) {
      renderReport(record.report);
      // Add to history
      if (!assessmentHistory.find(a => a.id === assessmentId)) {
        assessmentHistory.unshift(record);
      }
    }
  } catch (err) {
    logActivity('system', `Failed to load report: ${err.message}`);
  }
}

function renderReport(report) {
  const container = document.getElementById('resultsSection');
  container.classList.remove('hidden');

  const decisionColors = {
    APPROVED: 'text-emerald',
    CONDITIONAL_APPROVAL: 'text-amber',
    REJECTED: 'text-rose',
    ABSTAINED: 'text-muted',
  };

  const riskColors = {
    LOW: 'text-emerald',
    MEDIUM: 'text-amber',
    HIGH: 'text-rose',
    CRITICAL: 'text-rose',
  };

  const confidence = report.compliance_confidence || 0;
  const uncertaintyLabel = report.uncertainty === 'STRONG' ? 'Low' : report.uncertainty === 'MODERATE' ? 'Moderate' : 'High';
  const decisionText = report.decision.replace(/_/g, ' ');

  container.innerHTML = `
    <div class="card">
      <div class="card-header">
        <div class="card-title">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          Governance Assessment — ${escapeHtml(report.proposal_title)}
        </div>
        <button class="btn-secondary" onclick="restoreForm()">New Assessment</button>
      </div>
      <div class="card-body">

        <!-- Decision Header -->
        <div class="results-header">
          <div class="decision-badge ${report.decision}">
            <div class="decision-label">Final Decision</div>
            <div class="decision-value">${decisionText}</div>
            <div style="margin-top: 8px; font-size: 0.75rem; color: var(--text-muted);">
              ${formatProcessingTime(report.processing_time_seconds)}
            </div>
          </div>
          <div class="results-metrics">
            <div class="metric-card">
              <div class="metric-label">Overall Risk</div>
              <div class="metric-value ${riskColors[report.overall_risk] || 'text-amber'}">${report.overall_risk}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Compliance Confidence</div>
              <div class="metric-value ${confidence >= 0.7 ? 'text-emerald' : confidence >= 0.5 ? 'text-amber' : 'text-rose'}">${(confidence * 100).toFixed(0)}%</div>
              <div class="compliance-bar-wrap">
                <div class="compliance-bar-track">
                  <div class="compliance-bar-fill" style="width: ${confidence * 100}%"></div>
                </div>
              </div>
            </div>
            <div class="metric-card">
              <div class="metric-label">Uncertainty</div>
              <div class="metric-value text-cyan">${uncertaintyLabel}</div>
              <div class="metric-sub">Evidence quality</div>
            </div>
          </div>
        </div>

        <!-- Tabs -->
        <div class="tabs" id="reportTabs">
          <button class="tab-btn active" onclick="switchResultTab('tab-gov')">Overview</button>
          <button class="tab-btn" onclick="switchResultTab('tab-policy')">Policy</button>
          <button class="tab-btn" onclick="switchResultTab('tab-compliance')">Compliance</button>
          <button class="tab-btn" onclick="switchResultTab('tab-risk')">Risks</button>
          <button class="tab-btn" onclick="switchResultTab('tab-ethics')">Ethics</button>
          <button class="tab-btn" onclick="switchResultTab('tab-bias')">Bias</button>
          <button class="tab-btn" onclick="switchResultTab('tab-technical')">Technical</button>
          <button class="tab-btn" onclick="switchResultTab('tab-security')">Security</button>
          <button class="tab-btn" onclick="switchResultTab('tab-privacy')">Privacy</button>
          <button class="tab-btn" onclick="switchResultTab('tab-guardrail')">Guardrail</button>
        </div>

        <div class="results-content" style="padding: 1.5rem;">
          <div id="tab-gov" class="tab-pane active">${renderOverview(report)}</div>
          <div id="tab-policy" class="tab-pane">${renderPolicyTab(report)}</div>
          <div id="tab-compliance" class="tab-pane">${renderComplianceTab(report)}</div>
          <div id="tab-risk" class="tab-pane">${renderRisksTab(report)}</div>
          <div id="tab-ethics" class="tab-pane">${renderEthicsTab(report)}</div>
          <div id="tab-bias" class="tab-pane">${renderBiasTab(report)}</div>
          <div id="tab-technical" class="tab-pane">${renderTechnicalTab(report)}</div>
          <div id="tab-security" class="tab-pane">${renderSecurityTab(report)}</div>
          <div id="tab-privacy" class="tab-pane">${renderPrivacyTab(report)}</div>
          <div id="tab-guardrail" class="tab-pane">${renderGuardrailTab(report)}</div>
        </div>

      </div>
    </div>
  `;

  container.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderOverview(report) {
  const issues = (report.key_issues || []).map((issue, i) => `
    <div class="issue-item">
      <div class="issue-num">${i + 1}</div>
      <div>${escapeHtml(issue)}</div>
    </div>
  `).join('');

  const actions = (report.required_actions || []).map(a => `
    <div class="action-item">
      <div class="action-priority">P${a.priority}</div>
      <div class="action-content">
        <div class="action-title">${escapeHtml(a.title)}</div>
        <div class="action-desc">${escapeHtml(a.description)}</div>
      </div>
      <div class="action-category">${escapeHtml(a.category)}</div>
    </div>
  `).join('');

  const evidence = (report.evidence_citations || []).map(e => `
    <div class="evidence-item">${escapeHtml(e)}</div>
  `).join('');

  const debateSection = (report.agent_disagreements || []).length > 0 ? `
    <div class="debate-section" style="margin-top: 1.5rem;">
      <div class="debate-title">⚡ Agent Debate — Resolved Disagreements</div>
      ${(report.agent_disagreements || []).map((d, i) => `
        <div class="debate-item">
          <div class="debate-disagreement">${escapeHtml(d)}</div>
          ${report.debate_rounds?.[i]?.reasoning ? `<div class="debate-resolution">→ ${escapeHtml(report.debate_rounds[i].reasoning)}</div>` : ''}
        </div>
      `).join('')}
    </div>
  ` : '';

  const reasoning = report.governance_reasoning ? `
    <div style="margin-top: 1.5rem; padding: 1rem 1.25rem; background: rgba(255,255,255,0.02); border: 1px solid var(--border); border-radius: var(--radius-md);">
      <div style="font-size: 0.75rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.5rem;">Governance Reasoning</div>
      <div style="font-size: 0.875rem; color: var(--text-secondary); line-height: 1.7;">${escapeHtml(report.governance_reasoning)}</div>
    </div>
  ` : '';

  return `
    ${issues ? `<div style="margin-bottom: 1.5rem;"><h3 style="font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem;">Key Issues</h3><div class="issues-list">${issues}</div></div>` : ''}
    ${actions ? `<div style="margin-bottom: 1.5rem;"><h3 style="font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem;">Required Actions</h3><div class="actions-list">${actions}</div></div>` : ''}
    ${evidence ? `<div style="margin-bottom: 1.5rem;"><h3 style="font-size: 0.85rem; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem;">Evidence Citations</h3><div class="evidence-list">${evidence}</div></div>` : ''}
    ${reasoning}
    ${debateSection}
    ${renderResearch(report.research)}
    <div style="margin-top: 1.5rem; display: flex; gap: 1rem; font-size: 0.8rem; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;">
      <span>Tokens used: ${(report.total_tokens_used || 0).toLocaleString()}</span>
      <span>•</span>
      <span>Processing: ${formatProcessingTime(report.processing_time_seconds)}</span>
    </div>
  `;
}

function renderComplianceTab(report) {
  const output = report.compliance_output;
  if (!output?.requirement_assessments?.length) return `<div class="empty-state"><div class="empty-icon">📋</div><p>No compliance data available.</p></div>`;

  const items = output.requirement_assessments.map(a => `
    <div class="compliance-item">
      <div class="compliance-item-header">
        <span class="compliance-status-badge status-${a.status}">${a.status.replace(/_/g, ' ')}</span>
        <span class="compliance-req-title">${escapeHtml(a.requirement_title)}</span>
        <span class="compliance-confidence">conf: ${(a.confidence * 100).toFixed(0)}%</span>
      </div>
      <div class="compliance-reasoning">${escapeHtml(a.reasoning)}</div>
      ${a.gaps?.length ? `<div class="compliance-gaps">${a.gaps.map(g => `<div class="gap-item">${escapeHtml(g)}</div>`).join('')}</div>` : ''}
    </div>
  `).join('');

  return `
    <div style="margin-bottom: 1rem; display: flex; gap: 1rem; align-items: center;">
      <div style="font-size: 0.9rem; color: var(--text-secondary);">Overall: <strong style="color: var(--text-primary);">${output.overall_status.replace(/_/g, ' ')}</strong></div>
      <div style="font-size: 0.9rem; color: var(--text-secondary);">Score: <strong style="color: var(--text-primary);">${(output.overall_compliance_score * 100).toFixed(0)}%</strong></div>
    </div>
    <div class="compliance-list">${items}</div>
    ${renderResearch(output.research)}
  `;
}

function renderRisksTab(report) {
  const output = report.risk_output;
  if (!output?.risks?.length) return `<div class="empty-state"><div class="empty-icon">⚠️</div><p>No risk data available.</p></div>`;

  const items = output.risks.map(r => `
    <div class="risk-item">
      <div class="risk-header">
        <span class="risk-severity severity-${r.severity}">${r.severity}</span>
        <span class="risk-category">${escapeHtml(r.category)}</span>
        <span class="risk-title">${escapeHtml(r.title)}</span>
        <span class="risk-score">${(r.likelihood * r.impact).toFixed(2)}</span>
      </div>
      <div class="risk-desc">${escapeHtml(r.description)}</div>
      ${r.mitigation ? `<div class="risk-mitigation">↗ ${escapeHtml(r.mitigation)}</div>` : ''}
    </div>
  `).join('');

  return `
    <div style="margin-bottom: 1rem; display: flex; gap: 1rem; align-items: center;">
      <div style="font-size: 0.9rem; color: var(--text-secondary);">Overall Risk: <strong style="color: var(--text-primary);">${output.overall_risk_level}</strong></div>
      <div style="font-size: 0.9rem; color: var(--text-secondary);">Score: <strong style="color: var(--text-primary);">${(output.risk_score * 100).toFixed(0)}%</strong></div>
    </div>
    <div class="risk-list">${items}</div>
    ${renderResearch(output.research)}
  `;
}

function renderEthicsTab(report) {
  const output = report.ethics_output;
  if (!output?.dimensions?.length) return `<div class="empty-state"><div class="empty-icon">⚖️</div><p>No ethics data available.</p></div>`;

  const getBarColor = (score) => {
    if (score >= 0.7) return 'linear-gradient(90deg, #34d399, #22d3ee)';
    if (score >= 0.45) return 'linear-gradient(90deg, #fbbf24, #fb923c)';
    return 'linear-gradient(90deg, #f87171, #fb923c)';
  };

  const getScoreColor = (score) => {
    if (score >= 0.7) return 'var(--accent-emerald)';
    if (score >= 0.45) return 'var(--accent-amber)';
    return 'var(--accent-rose)';
  };

  const dims = output.dimensions.map(d => `
    <div class="ethics-dim">
      <div class="ethics-dim-header">
        <span class="ethics-dim-name">${d.dimension.replace(/_/g, ' ')}</span>
        <span class="ethics-score" style="color: ${getScoreColor(d.score)}">${(d.score * 100).toFixed(0)}%</span>
      </div>
      <div class="score-bar-track">
        <div class="score-bar-fill" style="width: ${d.score * 100}%; background: ${getBarColor(d.score)};"></div>
      </div>
      <div class="ethics-reasoning">${escapeHtml(d.reasoning)}</div>
    </div>
  `).join('');

  const sovereignty = output.sovereignty_concerns?.length ? `
    <div style="margin-top: 1.5rem; padding: 1rem 1.25rem; background: rgba(167,139,250,0.05); border: 1px solid rgba(167,139,250,0.2); border-radius: var(--radius-md);">
      <div style="font-size: 0.8rem; font-weight: 600; color: var(--accent-violet); margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em;">Digital Sovereignty Concerns</div>
      ${output.sovereignty_concerns.map(c => `<div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.5rem; padding-left: 1rem; border-left: 2px solid rgba(167,139,250,0.3);">${escapeHtml(c)}</div>`).join('')}
    </div>
  ` : '';

  return `
    <div style="margin-bottom: 1.25rem; font-size: 0.9rem; color: var(--text-secondary);">
      Overall Ethics Score: <strong style="color: var(--text-primary);">${(output.overall_score * 100).toFixed(0)}%</strong>
    </div>
    <div class="ethics-grid">${dims}</div>
    ${sovereignty}
    ${renderResearch(output.research)}
  `;
}

function renderResearch(research) {
  if (!research || !research.length) return '';
  const items = research.map(r => `
    <div style="margin-bottom: 0.75rem; padding: 0.75rem; background: rgba(255,255,255,0.02); border-left: 2px solid var(--accent-indigo);">
      <div style="font-size: 0.75rem; color: var(--accent-indigo); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.25rem;">🔍 Research Query</div>
      <div style="font-size: 0.85rem; font-weight: 500; margin-bottom: 0.5rem;">${escapeHtml(r.query)}</div>
      <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.5rem;">Certainty: ${r.certainty_score.toFixed(2)} | Sources: ${r.sources ? r.sources.length : 0}</div>
      <ul style="margin: 0; padding-left: 1rem; font-size: 0.8rem; color: var(--text-secondary);">
        ${(r.findings || []).map(f => `<li>${escapeHtml(f)}</li>`).join('')}
      </ul>
    </div>
  `).join('');
  return `<div style="margin-top: 1rem;"><h4 style="font-size: 0.8rem; margin-bottom: 0.5rem;">Sub-Agent Research Findings</h4><div style="border: 1px solid var(--border); border-radius: var(--radius-md); padding: 0.5rem;">${items}</div></div>`;
}

function renderTechnicalTab(report) {
  const output = report.technical_output;

  const debt = output.technical_debt?.length ? `
    <div style="margin-top: 1.5rem; padding: 1rem 1.25rem; background: rgba(34,211,238,0.04); border: 1px solid rgba(34,211,238,0.15); border-radius: var(--radius-md);">
      <div style="font-size: 0.8rem; font-weight: 600; color: var(--accent-cyan); margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.08em;">Technical Debt Items</div>
      ${output.technical_debt.map(d => `<div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.4rem;">• ${escapeHtml(d)}</div>`).join('')}
    </div>
  ` : '';

  return `
    <div style="margin-bottom: 1rem; display: flex; gap: 1rem; align-items: center;">
      <div style="font-size: 0.9rem; color: var(--text-secondary);">Architecture Compliant: 
        <strong style="color: ${output.architecture_compliant ? 'var(--accent-emerald)' : 'var(--accent-rose)'};">
          ${output.architecture_compliant ? 'Yes' : 'No'}
        </strong>
      </div>
    </div>
    <div class="tech-findings-list">${findings}</div>
    ${debt}
  `;
}

// ── Tab Switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(`tab-${name}`).classList.add('active');
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch('/api/assess');
    const items = await res.json();

    const container = document.getElementById('historyList');
    if (!items.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📊</div><p>No assessments yet. Submit a proposal to get started.</p></div>`;
      return;
    }

    const decisionStyle = {
      APPROVED: 'background: rgba(52,211,153,0.12); color: var(--accent-emerald);',
      CONDITIONAL_APPROVAL: 'background: rgba(251,191,36,0.12); color: var(--accent-amber);',
      REJECTED: 'background: rgba(248,113,113,0.12); color: var(--accent-rose);',
      ABSTAINED: 'background: rgba(148,163,184,0.12); color: var(--text-secondary);',
    };

    container.innerHTML = `<div class="history-list">
      ${items.map(item => `
        <div class="history-card" onclick="loadHistoricalReport('${item.id}')">
          <div style="flex: 1;">
            <div class="history-title">${escapeHtml(item.proposal_title)}</div>
            <div class="history-org">${item.status === 'running' ? '⏳ Running...' : formatDate(item.created_at)}</div>
          </div>
          ${item.decision ? `<span class="history-decision" style="${decisionStyle[item.decision] || ''}">${item.decision.replace(/_/g, ' ')}</span>` : `<span class="history-decision" style="background: rgba(148,163,184,0.1); color: var(--text-muted);">${item.status.toUpperCase()}</span>`}
          ${item.overall_risk ? `<span style="font-size: 0.8rem; color: var(--text-muted);">Risk: ${item.overall_risk}</span>` : ''}
          ${item.processing_time_seconds ? `<span class="history-time">${formatProcessingTime(item.processing_time_seconds)}</span>` : ''}
          <span class="history-arrow">›</span>
        </div>
      `).join('')}
    </div>`;
  } catch {}
}

async function loadHistoricalReport(assessmentId) {
  showSection('assess');
  document.getElementById('formCard').classList.add('hidden');
  showPipeline();
  document.getElementById('pipelineCard').classList.add('hidden');
  await loadAndRenderReport(assessmentId);
  document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

// ── Policies ──────────────────────────────────────────────────────────────────
async function loadPolicies() {
  const container = document.getElementById('policiesGrid');
  try {
    const res = await fetch('/api/policies');
    const data = await res.json();

    if (!data.sources?.length) {
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📚</div><p>No policy sources loaded.</p></div>`;
      return;
    }

    const typeColors = {
      regulation: '#818cf8', framework: '#22d3ee', guideline: '#34d399', standard: '#fbbf24'
    };

    container.innerHTML = `
      <div style="margin-bottom: 1.5rem; display: flex; gap: 2rem; align-items: center;">
        <div style="font-size: 0.9rem; color: var(--text-secondary);">
          <strong style="color: var(--text-primary);">${data.total_chunks}</strong> total policy chunks indexed
        </div>
        <div style="font-size: 0.9rem; color: var(--text-secondary);">
          Embedding model: <code style="color: var(--accent-cyan); font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;">${data.embedding_model}</code>
        </div>
        <div style="font-size: 0.9rem; color: ${data.status === 'ready' ? 'var(--accent-emerald)' : 'var(--accent-amber)'};">${data.status === 'ready' ? '✓ Ready' : '⚠ Empty'}</div>
      </div>
      <div class="policies-grid">
        ${data.sources.map(s => `
          <div class="policy-card">
            <div class="policy-card-header">
              <div class="policy-name">${escapeHtml(s.name)}</div>
              <div class="policy-type" style="color: ${typeColors[s.type] || 'var(--accent-primary)'};">${s.type}</div>
            </div>
            <div class="policy-meta">${s.jurisdiction} · v${s.version}</div>
            <div class="policy-desc">${escapeHtml(s.description.substring(0, 180))}${s.description.length > 180 ? '...' : ''}</div>
            <div class="policy-chunks">${s.chunk_count} chunks indexed</div>
          </div>
        `).join('')}
      </div>
    `;
  } catch {
    container.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div><p>Failed to load policies.</p></div>`;
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let icon = 'ℹ️';
  if (type === 'error') icon = '❌';
  if (type === 'success') icon = '✅';
  if (type === 'warning') icon = '⚠️';
  
  toast.innerHTML = `<strong style="margin-right:8px;">${icon}</strong> ${escapeHtml(message)}`;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.style.animation = 'toastSlideOut 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards';
    setTimeout(() => toast.remove(), 400);
  }, 4000);
}

function restoreForm() {
  document.getElementById('formCard').classList.remove('hidden');
  document.getElementById('pipelineCard').classList.add('hidden');
  document.getElementById('resultsSection').classList.add('hidden');
  document.getElementById('resultsSection').innerHTML = '';
  document.getElementById('activityEntries').innerHTML = '';
  document.getElementById('propFile').value = '';
  document.getElementById('fileUploadLabel').innerText = '';

  // Reset agent states
  document.querySelectorAll('.agent-node').forEach(n => {
    n.className = `agent-node${n.classList.contains('governance-node') ? ' governance-node' : ''} idle`;
    n.querySelector('.agent-status').className = 'agent-status idle';
    n.querySelector('.agent-status').textContent = 'Waiting';
  });

  const btn = document.getElementById('submitBtn');
  btn.disabled = false;
  btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Run Governance Assessment`;

  if (currentEventSource) {
    currentEventSource.close();
    currentEventSource = null;
  }
  currentAssessmentId = null;
  document.getElementById('formCard').scrollIntoView({ behavior: 'smooth' });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatProcessingTime(seconds) {
  if (!seconds) return '';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${Math.floor(seconds / 60)}m ${(seconds % 60).toFixed(0)}s`;
}

function formatDate(isoStr) {
  if (!isoStr) return '';
  return new Date(isoStr).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

// ── File Upload ───────────────────────────────────────────────────────────────
function updateFileLabel(input) {
  const el = document.getElementById('fileUploadLabel');
  if (input.files.length > 0) {
    el.innerText = input.files[0].name;
  } else {
    el.innerText = '';
  }
}

// ── Configuration ─────────────────────────────────────────────────────────────
let currentConfigData = null;

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    const config = await res.json();
    currentConfigData = config;
    if (!currentConfigData.agent_configs) currentConfigData.agent_configs = {};
    
    document.getElementById('cfgProvider').value = config.llm_provider || 'gemini';
    document.getElementById('cfgModel').value = config.llm_model || 'gemini/gemini-2.0-flash';
    document.getElementById('cfgTemp').value = config.llm_temperature || 0.1;
    document.getElementById('cfgTempVal').innerText = config.llm_temperature || 0.1;
    document.getElementById('cfgTokens').value = config.llm_max_tokens || 4096;
    
    // Mask API keys if they exist
    if (config.gemini_api_key) document.getElementById('cfgGeminiKey').placeholder = '•••••••••••••••• (Set)';
    if (config.openai_api_key) document.getElementById('cfgOpenAIKey').placeholder = '•••••••••••••••• (Set)';
    if (config.anthropic_api_key) document.getElementById('cfgAnthropicKey').placeholder = '•••••••••••••••• (Set)';
    if (config.groq_api_key) document.getElementById('cfgGroqKey').placeholder = '•••••••••••••••• (Set)';
    
    loadAgentConfig(); // populate the sub-form
  } catch (err) {
    console.error("Failed to load config", err);
  }
}

function loadAgentConfig() {
  if (!currentConfigData) return;
  const agentId = document.getElementById('cfgAgentSelect').value;
  const ac = currentConfigData.agent_configs[agentId] || {};
  
  document.getElementById('cfgAgentProvider').value = ac.llm_provider || '';
  document.getElementById('cfgAgentModel').value = ac.llm_model || '';
  
  if (ac.llm_temperature !== undefined && ac.llm_temperature !== null) {
    document.getElementById('cfgAgentTemp').value = ac.llm_temperature;
    document.getElementById('cfgAgentTempVal').innerText = ac.llm_temperature;
  } else {
    document.getElementById('cfgAgentTemp').value = 0.1;
    document.getElementById('cfgAgentTempVal').innerText = '--';
  }
  
  document.getElementById('cfgAgentTokens').value = ac.llm_max_tokens || '';
  document.getElementById('cfgAgentPrompt').value = ac.system_prompt || '';
}

function updateCurrentAgentConfig() {
  if (!currentConfigData) return;
  const agentId = document.getElementById('cfgAgentSelect').value;
  
  const provider = document.getElementById('cfgAgentProvider').value;
  const model = document.getElementById('cfgAgentModel').value;
  const tempStr = document.getElementById('cfgAgentTempVal').innerText;
  const tokens = document.getElementById('cfgAgentTokens').value;
  const prompt = document.getElementById('cfgAgentPrompt').value;
  
  const ac = {};
  if (provider) ac.llm_provider = provider;
  if (model) ac.llm_model = model;
  if (tempStr !== '--') ac.llm_temperature = parseFloat(document.getElementById('cfgAgentTemp').value);
  if (tokens) ac.llm_max_tokens = parseInt(tokens, 10);
  if (prompt) ac.system_prompt = prompt;
  
  currentConfigData.agent_configs[agentId] = ac;
}

async function saveConfig(event) {
  event.preventDefault();
  updateCurrentAgentConfig(); // commit the currently visible agent config to memory
  
  const btn = document.getElementById('saveConfigBtn');
  btn.innerHTML = `<div class="spinner"></div> Saving...`;
  btn.disabled = true;
  
  const payload = {
    llm_provider: document.getElementById('cfgProvider').value,
    llm_model: document.getElementById('cfgModel').value,
    llm_temperature: parseFloat(document.getElementById('cfgTemp').value),
    llm_max_tokens: parseInt(document.getElementById('cfgTokens').value, 10),
    agent_configs: currentConfigData.agent_configs,
  };
  
  // Only update keys if user typed something
  const gk = document.getElementById('cfgGeminiKey').value;
  const ok = document.getElementById('cfgOpenAIKey').value;
  const ak = document.getElementById('cfgAnthropicKey').value;
  const gqk = document.getElementById('cfgGroqKey').value;
  
  if (gk) payload.gemini_api_key = gk;
  if (ok) payload.openai_api_key = ok;
  if (ak) payload.anthropic_api_key = ak;
  if (gqk) payload.groq_api_key = gqk;

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Failed to save");
    
    // Clear passwords
    document.getElementById('cfgGeminiKey').value = '';
    document.getElementById('cfgOpenAIKey').value = '';
    document.getElementById('cfgAnthropicKey').value = '';
    document.getElementById('cfgGroqKey').value = '';
    
    btn.innerHTML = `Saved ✓`;
    btn.style.background = 'var(--accent-emerald)';
    setTimeout(() => {
      btn.innerHTML = `Save Configuration`;
      btn.style.background = '';
      btn.disabled = false;
      loadConfig();
    }, 2000);
  } catch (err) {
    alert("Failed to save config: " + err.message);
    btn.innerHTML = `Save Configuration`;
    btn.disabled = false;
  }
}
