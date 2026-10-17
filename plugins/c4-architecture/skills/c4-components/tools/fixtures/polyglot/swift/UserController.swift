import Vapor

struct UserController: RouteCollection {
    func boot(routes: RoutesBuilder) throws {
        routes.get("users", use: index)
        routes.post("users", use: create)
    }
}
