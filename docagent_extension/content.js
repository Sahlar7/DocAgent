console.log("DocAgent content script loaded");

class DocAgentSidebar {
  constructor() {
    this.isCollapsed = false;
    this.messageHistory = [];
    this.isInitialized = false;
    this.sessionId = this.generateSessionId();
    this.accessToken = null;
    this.backendUrl = "http://localhost:8000";
  }

  generateSessionId() {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  async initialize() {
    if (this.isInitialized) return;

    console.log("Initializing DocAgent extension");

    // Check if extension context is valid
    if (!this.checkExtensionContext()) {
      console.warn("DocAgent: Extension context is invalid, not initializing");
      return;
    }

    if (this.isGoogleDocsPage()) {
      // Try to get auth token
      try {
        await this.ensureAuthenticated();
        console.log("Authentication successful");
      } catch (error) {
        console.warn("Authentication failed, will prompt on first use:", error);
      }

      this.injectSidebar();
      this.isInitialized = true;
    }
  }

  checkExtensionContext() {
    try {
      return chrome.runtime && chrome.runtime.id;
    } catch (error) {
      console.warn("Extension context check failed:", error);
      return false;
    }
  }

  isGoogleDocsPage() {
    return (
      window.location.hostname === "docs.google.com" &&
      window.location.pathname.includes("/document/")
    );
  }

  /**
   * Ensure we have a valid OAuth token
   */
  async ensureAuthenticated(interactive = false) {
    if (this.accessToken) {
      return this.accessToken;
    }

    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: "GET_AUTH_TOKEN", interactive },
        (response) => {
          if (response && response.success) {
            this.accessToken = response.token;
            console.log("Access token obtained");
            resolve(response.token);
          } else {
            console.error("Failed to get access token:", response?.error);
            reject(new Error(response?.error || "Authentication failed"));
          }
        },
      );
    });
  }

  /**
   * Refresh the OAuth token
   */
  async refreshAuthToken() {
    this.accessToken = null;
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "REFRESH_AUTH_TOKEN" }, (response) => {
        if (response && response.success) {
          this.accessToken = response.token;
          resolve(response.token);
        } else {
          reject(new Error(response?.error || "Token refresh failed"));
        }
      });
    });
  }

  injectSidebar() {
    // Check if sidebar already exists
    if (document.getElementById("docagent-sidebar")) {
      console.log("Sidebar already exists, skipping injection");
      return;
    }

    console.log("Injecting sidebar into Google Docs");

    const sidebarContainer = document.createElement("div");
    sidebarContainer.id = "docagent-sidebar";
    sidebarContainer.innerHTML = `
      <div class="docagent-sidebar-header">
        <h3>DocAgent</h3>
        <div class="docagent-header-actions">
          <button id="docagent-clear-chat" title="Clear conversation">🗑️</button>
          <button id="docagent-toggle">×</button>
        </div>
      </div>
      <div class="docagent-sidebar-content">
        <div id="docagent-auth-notice" style="display: none; padding: 10px; background: #fff3cd; border-radius: 5px; margin-bottom: 10px;">
          <p style="margin: 0; font-size: 12px; color: #856404;">
            🔐 Authentication required. Click send to sign in.
          </p>
        </div>
        <div id="docagent-chat-messages"></div>
        <div class="docagent-input-container">
          <textarea id="docagent-message-input" placeholder="Ask DocAgent to write, edit, or analyze your document..."></textarea>
          <button id="docagent-send-btn">Send</button>
        </div>
      </div>
    `;

    document.body.appendChild(sidebarContainer);
    this.adjustSidebarPosition();
    this.setupEventListeners();

    // Show auth notice if not authenticated
    if (!this.accessToken) {
      document.getElementById("docagent-auth-notice").style.display = "block";
    }
  }

  adjustSidebarPosition() {
    const docsHeader =
      document.querySelector(".docs-titlebar-container") ||
      document.querySelector(".docs-chrome") ||
      document.querySelector("#docs-chrome") ||
      document.querySelector(".docs-material-header");

    let headerHeight = 64;

    if (docsHeader) {
      headerHeight = docsHeader.offsetHeight;
    }

    const sidebar = document.getElementById("docagent-sidebar");
    if (sidebar) {
      sidebar.style.top = `${headerHeight}px`;
      sidebar.style.height = `calc(100vh - ${headerHeight}px)`;
    }
  }

  setupEventListeners() {
    const toggleBtn = document.getElementById("docagent-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => this.toggle());
    }

    const clearBtn = document.getElementById("docagent-clear-chat");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => this.clearChat());
    }

    const sendBtn = document.getElementById("docagent-send-btn");
    const messageInput = document.getElementById("docagent-message-input");

    if (sendBtn) {
      sendBtn.addEventListener("click", () => this.sendMessage());
    }

    if (messageInput) {
      messageInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });
    }
  }

  toggle() {
    this.isCollapsed = !this.isCollapsed;
    const sidebar = document.getElementById("docagent-sidebar");
    if (sidebar) {
      sidebar.classList.toggle("collapsed", this.isCollapsed);
    }
  }

  async sendMessage() {
    const messageInput = document.getElementById("docagent-message-input");
    const message = messageInput.value.trim();

    if (!message) return;

    this.addMessage("user", message);
    messageInput.value = "";
    this.showLoadingMessage();

    try {
      // Ensure we have a valid token
      await this.ensureAuthenticated(true);

      // Hide auth notice if visible
      const authNotice = document.getElementById("docagent-auth-notice");
      if (authNotice) {
        authNotice.style.display = "none";
      }

      // Send to backend
      const response = await this.sendToBackend(message);

      this.removeLoadingMessage();

      if (response.success) {
        // Extract message string safely
        const messageText =
          typeof response.message === "string"
            ? response.message
            : JSON.stringify(response.message, null, 2);

        this.addMessage("assistant", messageText);

        if (response.requires_approval && response.request_id) {
          this.showApprovalButtons(response);
        }
      } else {
        this.addMessage(
          "assistant",
          `Error: ${response.error || response.message || "Unknown error occurred"}`,
        );
      }
    } catch (error) {
      console.error("Error sending message:", error);
      this.removeLoadingMessage();

      // Check if it's an auth error
      if (error.message.includes("401") || error.message.includes("auth")) {
        this.addMessage(
          "assistant",
          "Authentication failed. Trying to refresh token...",
        );
        try {
          await this.refreshAuthToken();
          this.addMessage(
            "assistant",
            "Token refreshed! Please try your request again.",
          );
        } catch (refreshError) {
          this.addMessage(
            "assistant",
            "Could not authenticate. Please reload the extension.",
          );
        }
      } else {
        this.addMessage("assistant", `Error: ${error.message}`);
      }
    }
  }

  async sendToBackend(message) {
    const documentId = this.getDocumentId();

    if (!documentId) {
      throw new Error("Could not extract document ID from URL");
    }

    if (!this.accessToken) {
      throw new Error("No access token available");
    }

    const response = await fetch(`${this.backendUrl}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.accessToken}`,
      },
      body: JSON.stringify({
        document_id: documentId,
        user_request: message,
        session_id: this.sessionId,
      }),
    });

    if (response.status === 401) {
      // Token expired or invalid
      throw new Error("401: Authentication failed");
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  }

  getDocumentId() {
    const url = window.location.href;
    const match = url.match(/\/document\/d\/([a-zA-Z0-9-_]+)/);
    return match ? match[1] : null;
  }

  showApprovalButtons(response) {
    console.log(
      "🔘 Showing approval buttons for request:",
      response.request_id,
    );

    const preview =
      response.batch_request?.preview ||
      response.preview ||
      "Pending operation";

    const chatMessages = document.getElementById("docagent-chat-messages");
    if (!chatMessages) return;

    const approvalElement = document.createElement("div");
    approvalElement.className = "docagent-approval-buttons";

    const containerDiv = document.createElement("div");
    containerDiv.style.cssText =
      "margin: 10px 0; padding: 12px; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px;";

    const descriptionP = document.createElement("p");
    descriptionP.style.cssText =
      "margin: 0 0 10px 0; font-size: 13px; color: #495057; font-weight: 500;";
    descriptionP.textContent = "⚠️ This operation requires your approval:";

    const previewP = document.createElement("p");
    previewP.style.cssText =
      "margin: 0 0 12px 0; font-size: 12px; color: #6c757d; font-style: italic;";
    previewP.textContent = preview;

    const buttonContainer = document.createElement("div");
    buttonContainer.style.cssText = "display: flex; gap: 8px;";

    const approveBtn = document.createElement("button");
    approveBtn.style.cssText =
      "flex: 1; background: #28a745; color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; font-weight: 500; transition: background 0.2s;";
    approveBtn.textContent = "✓ Approve";
    approveBtn.onmouseover = () => (approveBtn.style.background = "#218838");
    approveBtn.onmouseout = () => (approveBtn.style.background = "#28a745");
    approveBtn.addEventListener("click", () =>
      this.handleApproval(true, response.request_id, containerDiv),
    );

    const rejectBtn = document.createElement("button");
    rejectBtn.style.cssText =
      "flex: 1; background: #dc3545; color: white; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; font-weight: 500; transition: background 0.2s;";
    rejectBtn.textContent = "✗ Reject";
    rejectBtn.onmouseover = () => (rejectBtn.style.background = "#c82333");
    rejectBtn.onmouseout = () => (rejectBtn.style.background = "#dc3545");
    rejectBtn.addEventListener("click", () =>
      this.handleApproval(false, response.request_id, containerDiv),
    );

    buttonContainer.appendChild(approveBtn);
    buttonContainer.appendChild(rejectBtn);

    containerDiv.appendChild(descriptionP);
    containerDiv.appendChild(previewP);
    containerDiv.appendChild(buttonContainer);
    approvalElement.appendChild(containerDiv);

    chatMessages.appendChild(approvalElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async handleApproval(approved, requestId, buttonContainer) {
    console.log("🔄 Processing approval:", { approved, requestId });

    if (!requestId) {
      this.addMessage("assistant", "❌ Error: No request ID found");
      return;
    }

    // Disable buttons
    buttonContainer.style.opacity = "0.5";
    buttonContainer.style.pointerEvents = "none";
    const statusP = document.createElement("p");
    statusP.style.cssText =
      "margin: 10px 0 0 0; font-size: 12px; color: #6c757d;";
    statusP.textContent = "⏳ Processing...";
    buttonContainer.appendChild(statusP);

    try {
      const response = await fetch(
        `${this.backendUrl}/api/approve/${requestId}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            approved: approved,
          }),
        },
      );

      const result = await response.json();

      if (result.success) {
        const message = approved
          ? "✅ Changes approved and applied successfully!"
          : "❌ Changes rejected. No modifications were made.";
        this.addMessage("assistant", message);
      } else {
        this.addMessage(
          "assistant",
          `❌ Error: ${result.error || "Approval failed"}`,
        );
      }
    } catch (error) {
      console.error("❌ Approval failed:", error);
      this.addMessage(
        "assistant",
        `❌ Failed to process approval: ${error.message}`,
      );
    }

    // Remove approval buttons
    const approvalButtons = buttonContainer.closest(
      ".docagent-approval-buttons",
    );
    if (approvalButtons) {
      approvalButtons.remove();
    }
  }

  showLoadingMessage() {
    const chatMessages = document.getElementById("docagent-chat-messages");
    if (!chatMessages) return;

    const loadingElement = document.createElement("div");
    loadingElement.id = "docagent-loading";
    loadingElement.className =
      "docagent-message docagent-message-assistant docagent-loading";
    loadingElement.innerHTML = "<span>🤔 DocAgent is thinking...</span>";

    chatMessages.appendChild(loadingElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  removeLoadingMessage() {
    const loadingElement = document.getElementById("docagent-loading");
    if (loadingElement) {
      loadingElement.remove();
    }
  }

  addMessage(sender, content) {
    const messageData = { sender, content, timestamp: Date.now() };
    this.messageHistory.push(messageData);
    this.renderMessage(messageData);
  }

  renderMessage(messageData) {
    const chatMessages = document.getElementById("docagent-chat-messages");
    if (!chatMessages) return;

    const messageElement = document.createElement("div");
    messageElement.className = `docagent-message docagent-message-${messageData.sender}`;

    // Always ensure content is a string
    const content = messageData.content;
    if (typeof content === "string") {
      messageElement.textContent = content;
    } else if (content === null || content === undefined) {
      messageElement.textContent = "(no response)";
    } else {
      messageElement.textContent = JSON.stringify(content, null, 2);
    }

    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async clearChat() {
    if (!confirm("Clear conversation history? This cannot be undone.")) {
      return;
    }

    this.messageHistory = [];
    const chatMessages = document.getElementById("docagent-chat-messages");
    if (chatMessages) {
      chatMessages.innerHTML = "";
    }

    // Clear session on backend
    try {
      await fetch(`${this.backendUrl}/api/session/${this.sessionId}`, {
        method: "DELETE",
      });
      // Generate new session ID
      this.sessionId = this.generateSessionId();
      console.log("✅ Session cleared, new session:", this.sessionId);
    } catch (error) {
      console.error("Failed to clear session on backend:", error);
    }

    this.addMessage(
      "assistant",
      "🔄 Conversation cleared. How can I help you?",
    );
  }
}

// Initialize the sidebar
const docAgentSidebar = new DocAgentSidebar();

// Global error handler
window.addEventListener("error", (event) => {
  if (
    event.error &&
    event.error.message &&
    event.error.message.includes("Extension context invalidated")
  ) {
    console.warn("DocAgent: Extension context invalidated");
  }
});

// Message listener
chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  if (request.type === "TOGGLE_SIDEBAR") {
    docAgentSidebar.toggle();
    sendResponse({ success: true });
  }
});

// Initialize when ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () =>
    docAgentSidebar.initialize(),
  );
} else {
  docAgentSidebar.initialize();
}

// Handle SPA navigation
let lastUrl = location.href;
new MutationObserver(() => {
  const url = location.href;
  if (url !== lastUrl) {
    lastUrl = url;
    setTimeout(() => docAgentSidebar.initialize(), 1000);
  }
}).observe(document, { subtree: true, childList: true });

console.log("DocAgent content script ready with OAuth support");
