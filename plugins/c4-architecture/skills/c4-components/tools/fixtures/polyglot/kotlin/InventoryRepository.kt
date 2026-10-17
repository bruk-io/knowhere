package inventory
import org.springframework.data.jpa.repository.JpaRepository

interface InventoryRepository : JpaRepository<Item, Long>
