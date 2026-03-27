import gradio as gr
from app.services.chat import chat_with_docs

# Function to handle user input
def handle_query(user_input):
    answer, sources = chat_with_docs(user_input)
    # Display sources nicely
    sources_text = "\n\n".join([f"Source: {src}" for src in sources])
    return answer, sources_text

# Gradio UI
iface = gr.Interface(
    fn=handle_query,
    inputs=gr.Textbox(lines=3, placeholder="Ask your question here..."),
    outputs=[gr.Textbox(label="Answer"), gr.Textbox(label="Sources")],
    title="Documind AI Co-pilot",
    description="Upload your docs in the backend and ask questions. Answers are based on the documents."
)

if __name__ == "__main__":
    iface.launch(share=True)