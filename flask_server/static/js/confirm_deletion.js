function confirmDeletion(event, form) {
    event.preventDefault();
    if (confirm("Você tem certeza que deseja deletar esta história?")) {
        form.submit();
    }
}