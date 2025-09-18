"""
Documents list modal component
"""
import streamlit as st
from datetime import datetime
from utils.api_client import api_client


def render_documents_modal():
    """Render documents list as a modal-like overlay"""
    if not st.session_state.show_documents_modal:
        return

    # Create a modal-like container with custom styling
    st.markdown("""
        <style>
        .modal-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            z-index: 999;
        }
        .modal-content {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin: 50px auto;
            max-width: 90%;
            max-height: 80vh;
            overflow-y: auto;
            position: relative;
            z-index: 1000;
        }
        </style>
    """, unsafe_allow_html=True)

    # Modal container
    with st.container():
        col1, col2, col3 = st.columns([1, 8, 1])

        with col2:
            # Modal header
            header_cols = st.columns([8, 1, 1])
            with header_cols[0]:
                st.markdown("### 📚 Knowledge Base Dokümanları")
            with header_cols[1]:
                if st.button("🔄", help="Yenile", key="refresh_docs_modal"):
                    st.session_state.knowledge_base_documents = api_client.fetch_documents()
                    st.rerun()
            with header_cols[2]:
                if st.button("❌", help="Kapat", key="close_modal"):
                    st.session_state.show_documents_modal = False
                    st.rerun()

            st.divider()

            # Search input
            search_query = st.text_input(
                "🔍 Doküman Ara",
                placeholder="Doküman adını yazın...",
                key="doc_search_modal",
                label_visibility="collapsed"
            )

            # Fetch documents if not already loaded
            if not st.session_state.knowledge_base_documents:
                with st.spinner("Dokümanlar yükleniyor..."):
                    st.session_state.knowledge_base_documents = api_client.fetch_documents()

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

                st.info(f"📊 Toplam {len(filtered_docs)} / {len(st.session_state.knowledge_base_documents)} doküman")

                # Create scrollable container
                container = st.container()
                with container:
                    # Display documents
                    for idx, doc in enumerate(filtered_docs):
                        doc_cols = st.columns([4, 2, 2, 1])

                        with doc_cols[0]:
                            st.write(f"📄 **{doc.get('title', 'Bilinmeyen')}**")
                            # Show URL if available
                            doc_url = doc.get('url')
                            if doc_url:
                                st.caption(f"🔗 [İndir]({doc_url})")
                            else:
                                st.caption("🔗 URL bulunamadı")

                        with doc_cols[1]:
                            st.write(f"📦 {doc.get('chunks_count', 0)} parça")

                        with doc_cols[2]:
                            created_at = doc.get('created_at', '')
                            if created_at:
                                try:
                                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                    formatted_date = date_obj.strftime("%d/%m/%Y %H:%M")
                                    st.write(f"📅 {formatted_date}")
                                except:
                                    st.write(f"📅 {created_at[:10]}")

                        with doc_cols[3]:
                            if st.button("🗑️", key=f"del_modal_{doc.get('document_id')}", help="Sil"):
                                doc_id = doc.get('document_id')
                                doc_title = doc.get('title', 'Bilinmeyen')

                                with st.spinner(f"'{doc_title}' siliniyor..."):
                                    success, result = api_client.delete_document(doc_id)

                                    if success:
                                        # Immediately remove from local state
                                        st.session_state.knowledge_base_documents = [
                                            d for d in st.session_state.knowledge_base_documents
                                            if d.get('document_id') != doc_id
                                        ]
                                        st.success(f"✅ '{doc_title}' başarıyla silindi!")
                                        # Rerun to update the display
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Silme başarısız: {result}")

                        st.divider()
            else:
                st.warning("📭 Knowledge base'de henüz doküman bulunmuyor.")
                st.info("💡 PDF yüklemek için sol taraftaki dosya yükleme butonunu kullanabilirsiniz.")