
document.addEventListener("DOMContentLoaded", () => {
    const slots = document.querySelectorAll(".slot");
    const employees = document.querySelectorAll(".employee");

    employees.forEach(emp => {
        emp.draggable = true;
        emp.addEventListener("dragstart", e => {
            e.dataTransfer.setData("text/plain", emp.dataset.empId);
        });
    });

    slots.forEach(slot => {
        slot.addEventListener("dragover", e => e.preventDefault());
        slot.addEventListener("drop", e => {
            const empId = e.dataTransfer.getData("text/plain");
            fetch(`/admin/assign`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ shift_id: slot.dataset.shiftId, employee_id: empId })
            }).then(() => location.reload());
        });
    });
});
