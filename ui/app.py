# ui/app.py
# Streamlit Human-in-the-Loop Approval UI
# Run with: streamlit run ui/app.py

import streamlit as st
import requests
import json

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Stale Content Refresh Agent", layout="wide")
st.title("🔄 Stale Content Refresh Agent")

# Init session state
if "processing" not in st.session_state:
    st.session_state.processing = False


def fetch_queue():
    try:
        r = requests.get(f"{API_BASE}/queue")
        return r.json()
    except Exception as e:
        st.error(f"Cannot connect to API: {e}")
        return {"pending": 0, "items": []}


def fetch_audit():
    try:
        r = requests.get(f"{API_BASE}/audit")
        return r.json()
    except Exception as e:
        st.error(f"Cannot connect to API: {e}")
        return {"total": 0, "items": []}


def trigger_scan():
    try:
        r = requests.post(f"{API_BASE}/scan")
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ── Sidebar ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Controls")

    if st.button("🔍 Run Scan", use_container_width=True):
        with st.spinner("Scanning AEM for stale pages..."):
            result = trigger_scan()
        if "error" in result:
            st.error(result["error"])
        elif result.get("processed", 0) == 0:
            st.warning("No stale pages found. Try increasing STALE_THRESHOLD_DAYS.")
        else:
            st.success(f"✅ Processed: {result.get('processed', 0)} | Skipped: {result.get('skipped', 0)}")
        st.rerun()

    st.divider()
    st.caption("Models")
    st.caption("🧠 Reasoning: qwen-plus")
    st.caption("✍️ Generation: qwen-max")

    try:
        health = requests.get(f"{API_BASE}/health").json()
        st.divider()
        st.caption("Token Usage")
        st.caption(f"Input:  {health['tokens_used']['input']}")
        st.caption(f"Output: {health['tokens_used']['output']}")
    except:
        pass


# ── Tabs ─────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📋 Review Queue", "📜 Audit Log"])


# ── Tab 1: Review Queue ───────────────────────────────────
with tab1:
    queue_data = fetch_queue()
    pending = queue_data.get("pending", 0)
    items = queue_data.get("items", [])

    st.subheader(f"Pending Review: {pending}")

    if not items:
        st.info("No items pending. Click 'Run Scan' in the sidebar to scan AEM.")

    for item in items:
        entry_id = item["id"]
        path = item["page_path"]
        timestamp = item["timestamp"][:19].replace("T", " ")
        original = item["original_content"]
        refreshed = item["refreshed_content"]
        reasoning = item["reasoning"]

        # Get last modified from jcr_tree
        jcr_tree = original.get("jcr_tree", {})
        jcr_content = jcr_tree.get("jcr:content", {})
        last_modified = jcr_content.get("cq:lastModified", "unknown")

        with st.expander(f"📄 {path}  |  Last modified: {last_modified}", expanded=True):

            # Staleness reasoning
            st.markdown("**🧠 Why it's stale:**")
            st.info(reasoning.get("staleness_reason", ""))

            st.markdown("**📌 Refresh direction:**")
            st.caption(reasoning.get("refresh_direction", ""))

            st.divider()

            # Diff view — what the model changed
            st.markdown("**📋 Content Changes Preview**")

            original_tree = original.get("jcr_tree", {})
            refreshed_tree = refreshed.get("jcr_tree", {})

            SKIP_KEYS = {
                "jcr:primaryType", "sling:resourceType", "jcr:created",
                "jcr:createdBy", "jcr:lastModified", "jcr:lastModifiedBy",
                "cq:template", "cq:lastModified", "cq:lastModifiedBy",
                "layout", "textIsRich", "jcr:mixinTypes", "singleExpansion",
                "jcr:created", "agent:bodyCopy"
            }

            CONTENT_KEYS = {"jcr:title", "jcr:description", "text", "cq:panelTitle"}

            def collect_ui_changes(orig, mod, current_path=""):
                diffs = []
                for key, new_val in mod.items():
                    if key in SKIP_KEYS:
                        continue
                    orig_val = orig.get(key) if isinstance(orig, dict) else None
                    if isinstance(new_val, dict):
                        diffs.extend(collect_ui_changes(
                            orig_val or {},
                            new_val,
                            f"{current_path}/{key}" if current_path else key
                        ))
                    elif isinstance(new_val, str) and key in CONTENT_KEYS and new_val != orig_val:
                        diffs.append({
                            "path": f"{current_path}/{key}" if current_path else key,
                            "original": orig_val or "empty",
                            "refreshed": new_val
                        })
                return diffs

            diffs = collect_ui_changes(original_tree, refreshed_tree)

            if diffs:
                for diff in diffs:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"📍 `{diff['path']}`")
                        st.markdown("**Original:**")
                        st.caption(diff["original"])
                    with col2:
                        st.caption(f"📍 `{diff['path']}`")
                        st.markdown("**Refreshed:**")
                        st.caption(diff["refreshed"])
                    st.divider()
            else:
                st.caption("No content differences detected — model may have returned unchanged content.")

            st.divider()

            # Action buttons
            col_approve, col_edit, col_reject = st.columns(3)

            with col_approve:
                if st.button("✅ Approve", key=f"approve_{entry_id}", use_container_width=True):
                    with st.spinner("Writing to JCR..."):
                        r = requests.post(f"{API_BASE}/approve/{entry_id}", json={})
                    if r.status_code == 200:
                        st.success("Approved!")
                        st.rerun()
                    else:
                        st.error(f"Failed to approve: {r.text}")

            with col_edit:
                if st.button("✏️ Edit + Approve", key=f"edit_{entry_id}", use_container_width=True):
                    st.session_state[f"editing_{entry_id}"] = True

            with col_reject:
                if st.button("❌ Reject", key=f"reject_{entry_id}", use_container_width=True):
                    st.session_state[f"rejecting_{entry_id}"] = True

            # Edit mode
            if st.session_state.get(f"editing_{entry_id}"):
                st.markdown("**✏️ Edit before approving:**")

                # Extract editable fields from refreshed jcr_tree
                ref_tree = refreshed.get("jcr_tree", {}) if isinstance(refreshed, dict) else {}
                ref_jcr = ref_tree.get("jcr:content", {})

                edited_title = st.text_input(
                    "Title",
                    value=ref_jcr.get("jcr:title", ""),
                    key=f"title_{entry_id}"
                )
                edited_desc = st.text_input(
                    "Description",
                    value=ref_jcr.get("jcr:description", ""),
                    key=f"desc_{entry_id}"
                )

                # Extract text component values from refreshed tree for editing
                def get_text_nodes(node, current_path="", results=None):
                    if results is None:
                        results = []
                    for key, value in node.items():
                        if not isinstance(value, dict):
                            continue
                        if "text" in value and isinstance(value["text"], str):
                            results.append({
                                "path": f"{current_path}/{key}" if current_path else key,
                                "key": key,
                                "text": value["text"]
                            })
                        get_text_nodes(value, f"{current_path}/{key}" if current_path else key, results)
                    return results

                ref_text_nodes = get_text_nodes(ref_tree)
                edited_text_nodes = {}

                if ref_text_nodes:
                    st.markdown("**Text Components:**")
                    for node in ref_text_nodes:
                        edited_text_nodes[node["path"]] = st.text_area(
                            f"`{node['key']}`",
                            value=node["text"],
                            height=100,
                            key=f"textnode_{entry_id}_{node['path'].replace('/', '_')}"
                        )

                col_submit, col_cancel_edit = st.columns(2)
                with col_submit:
                    if st.button("💾 Submit Edits", key=f"submit_{entry_id}", use_container_width=True):
                        # Rebuild modified jcr_tree with edited values
                        import copy
                        edited_tree = copy.deepcopy(ref_tree)

                        # Apply title and description edits
                        if "jcr:content" in edited_tree:
                            edited_tree["jcr:content"]["jcr:title"] = edited_title
                            edited_tree["jcr:content"]["jcr:description"] = edited_desc

                        # Apply text node edits
                        def apply_text_edits(node, current_path=""):
                            for key, value in node.items():
                                if not isinstance(value, dict):
                                    continue
                                node_path = f"{current_path}/{key}" if current_path else key
                                if node_path in edited_text_nodes:
                                    value["text"] = edited_text_nodes[node_path]
                                apply_text_edits(value, node_path)

                        apply_text_edits(edited_tree)

                        edited_content = {
                            "path": refreshed.get("path", path),
                            "jcr_tree": edited_tree
                        }

                        with st.spinner("Writing to JCR..."):
                            r = requests.post(
                                f"{API_BASE}/approve/{entry_id}",
                                json={"edited_content": edited_content}
                            )
                        if r.status_code == 200:
                            st.success("Approved with edits!")
                            del st.session_state[f"editing_{entry_id}"]
                            st.rerun()
                        else:
                            st.error(f"Failed to approve: {r.text}")

                with col_cancel_edit:
                    if st.button("Cancel", key=f"cancel_edit_{entry_id}", use_container_width=True):
                        del st.session_state[f"editing_{entry_id}"]
                        st.rerun()

            # Reject mode
            if st.session_state.get(f"rejecting_{entry_id}"):
                st.markdown("**❌ Rejection reason:**")
                reason = st.selectbox(
                    "Select reason",
                    ["Content not relevant", "Wrong tone", "Factually incorrect", "Other"],
                    key=f"reason_select_{entry_id}"
                )
                extra = st.text_input("Additional notes (optional)", key=f"reason_extra_{entry_id}")

                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("Confirm Reject", key=f"confirm_reject_{entry_id}", use_container_width=True):
                        full_reason = f"{reason}. {extra}".strip(". ")
                        with st.spinner("Rejecting..."):
                            r = requests.post(
                                f"{API_BASE}/reject/{entry_id}",
                                json={"reason": full_reason}
                            )
                        if r.status_code == 200:
                            st.warning("Rejected.")
                            del st.session_state[f"rejecting_{entry_id}"]
                            st.rerun()
                        else:
                            st.error(f"Failed to reject: {r.text}")
                with col_cancel:
                    if st.button("Cancel", key=f"cancel_reject_{entry_id}", use_container_width=True):
                        del st.session_state[f"rejecting_{entry_id}"]
                        st.rerun()


# ── Tab 2: Audit Log ──────────────────────────────────────
with tab2:
    audit_data = fetch_audit()
    all_items = audit_data.get("items", [])

    st.subheader(f"Total entries: {audit_data.get('total', 0)}")

    approved = [i for i in all_items if i["reviewer_action"] == "approved"]
    rejected = [i for i in all_items if i["reviewer_action"] == "rejected"]
    pending_items = [i for i in all_items if i["reviewer_action"] == "pending"]

    col1, col2, col3 = st.columns(3)
    col1.metric("✅ Approved", len(approved))
    col2.metric("❌ Rejected", len(rejected))
    col3.metric("⏳ Pending", len(pending_items))

    st.divider()

    for item in all_items:
        action = item["reviewer_action"]
        icon = "✅" if action == "approved" else "❌" if action == "rejected" else "⏳"
        timestamp = item["timestamp"][:19].replace("T", " ")

        with st.expander(f"{icon} {item['page_path']}  |  {timestamp}"):
            st.caption(f"Action: {action}")
            if item.get("reviewer_edits"):
                st.caption(f"Edits: {item['reviewer_edits']}")

            # New shape: refreshed is { path, jcr_tree }
            refreshed = item["refreshed_content"]
            refreshed_tree = refreshed.get("jcr_tree", {}) if isinstance(refreshed, dict) else {}
            refreshed_jcr = refreshed_tree.get("jcr:content", {})

            st.markdown(f"**Title:** {refreshed_jcr.get('jcr:title', '') or 'not set'}")
            st.markdown(f"**Description:** {refreshed_jcr.get('jcr:description', '') or 'not set'}")

            # Rollback — only for approved entries not yet rolled back
            if action == "approved" and not item.get("rolled_back"):
                st.divider()
                if st.button("↩️ Rollback", key=f"rollback_{item['id']}", use_container_width=True):
                    st.session_state[f"confirm_rollback_{item['id']}"] = True

                if st.session_state.get(f"confirm_rollback_{item['id']}"):
                    st.warning("Are you sure? This will restore the original content in AEM.")
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("Yes, rollback", key=f"confirm_yes_{item['id']}", use_container_width=True):
                            with st.spinner("Rolling back..."):
                                r = requests.post(f"{API_BASE}/rollback/{item['id']}")
                            if r.status_code == 200:
                                st.success("Rolled back successfully!")
                                del st.session_state[f"confirm_rollback_{item['id']}"]
                                st.rerun()
                            else:
                                st.error(f"Rollback failed: {r.text}")
                    with col_no:
                        if st.button("Cancel", key=f"confirm_no_{item['id']}", use_container_width=True):
                            del st.session_state[f"confirm_rollback_{item['id']}"]
                            st.rerun()

            elif item.get("rolled_back"):
                st.caption("↩️ This entry has been rolled back")