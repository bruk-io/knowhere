package orders;

import org.springframework.data.jpa.repository.JpaRepository;

// Spring Data repository: interface extending *Repository, NO @Repository annotation.
public interface OrderRepository extends JpaRepository<Order, Long> {
}
