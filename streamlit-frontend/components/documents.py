"""
Documents list component
"""
import streamlit as st
from datetime import datetime
from utils.api_client import api_client


def render_documents_modal():
    """Render the documents list modal"""
    if not st.session_state.show_documents_list:
        return

    # Create placeholder at top to prevent auto-scroll to bottom
    docs_container = st.container()

    with docs_container:
        st.markdown("---")
        col1, col2 = st.columns([8, 2])

        with col1:
            st.markdown("### 📚 Knowledge Base Dokümanları")

        with col2:
            button_cols = st.columns(3)
            with button_cols[0]:
                if st.button("🔄", help="Yenile", key="refresh_docs"):
                    st.session_state.knowledge_base_documents = api_client.fetch_documents()
                    st.rerun()
            with button_cols[1]:
                if st.button("❌", help="Kapat", key="close_docs"):
                    st.session_state.show_documents_list = False
                    st.rerun()

        # Search input
        search_query = st.text_input(
            "🔍 Doküman Ara",
            placeholder="Doküman adını yazın (Enter ile ara)...",
            key="doc_search_input",
            label_visibility="collapsed"
        )

        if st.session_state.knowledge_base_documents:
            # Sort documents: numbers first, then alphabetically
            sorted_docs = sorted(
                st.session_state.knowledge_base_documents,
                key=lambda x: (
                    not x.get('title', '').replace('.pdf', '')[0].isdigit() if x.get('title', '') else True,
                    x.get('title', '').lower().replace('.pdf', '')
                )
            )

            # Filter documents based on search query
            if search_query:
                filtered_docs = [
                    doc for doc in sorted_docs
                    if search_query.lower() in doc.get('title', '').lower()
                ]
            else:
                filtered_docs = sorted_docs

            st.info(f"📊 Toplam {len(filtered_docs)} / {len(st.session_state.knowledge_base_documents)} doküman gösteriliyor")

            # Create scrollable container with fixed height
            with st.container():
                # Add CSS for scrollable container
                st.markdown("""
                    <style>
                    .docs-list-container {
                        max-height: 400px;
                        overflow-y: auto;
                        padding: 10px;
                    }
                    </style>
                """, unsafe_allow_html=True)

                # Create a table-like view
                for idx, doc in enumerate(filtered_docs):
                    with st.container():
                        col1, col2, col3, col4 = st.columns([4, 2, 2, 1])

                        with col1:
                            st.write(f"📄 **{doc.get('title', 'Bilinmeyen')}**")
                            # Show URL if available, otherwise show "URL bulunamadı"
                            doc_url = doc.get('url')
                            if doc_url:
                                st.caption(f"🔗 [İndir]({doc_url})")
                            else:
                                st.caption("🔗 URL bulunamadı")

                        with col2:
                            st.write(f"📦 {doc.get('chunks_count', 0)} parça")

                        with col3:
                            created_at = doc.get('created_at', '')
                            if created_at:
                                try:
                                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                                    st.write(f"📅 {formatted_date}")
                                except:
                                    st.write(f"📅 {created_at[:10]}")

                        with col4:
                            if st.button("🗑️", key=f"del_{doc.get('document_id')}", help="Sil"):
                                doc_id = doc.get('document_id')
                                doc_title = doc.get('title', 'Bilinmeyen')

                                with st.spinner(f"'{doc_title}' siliniyor..."):
                                    success, result = api_client.delete_document(doc_id)

                                    if success:
                                        st.success(f"✅ '{doc_title}' başarıyla silindi!")
                                        # Refresh the list
                                        st.session_state.knowledge_base_documents = api_client.fetch_documents()
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Silme başarısız: {result}")

                        st.markdown("---")
        else:
            st.warning("📭 Knowledge base'de henüz doküman bulunmuyor.")
            st.info("💡 PDF yüklemek için sol taraftaki dosya yükleme butonunu kullanabilirsiniz.")